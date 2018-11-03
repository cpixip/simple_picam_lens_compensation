# for stream handling
import io

# need to wait a few secs
from time import sleep

# the picamera-lib
from picamera import PiCamera

# for some computations
import cv2
import numpy as np

# for reading back a table
import string

# structure to read out raw image information
# from https://picamera.readthedocs.io/en/release-1.13/_modules/picamera/array.html#PiBayerArray
import ctypes as ct
class BroadcomRawHeader(ct.Structure):
    _fields_ = [
        ('name',          ct.c_char * 32),
        ('width',         ct.c_uint16),
        ('height',        ct.c_uint16),
        ('padding_right', ct.c_uint16),
        ('padding_down',  ct.c_uint16),
        ('dummy',         ct.c_uint32 * 6),
        ('transform',     ct.c_uint16),
        ('format',        ct.c_uint16),
        ('bayer_order',   ct.c_uint8),
        ('bayer_format',  ct.c_uint8),
        ]

# reads the raw part of a v1-camera jpg
# and sorts it into the appropriate color channels        
def readRaw(data):

    # check again for header
    assert data[:4] == 'BRCM'

    # extract raw data
    # from https://picamera.readthedocs.io/en/release-1.13/_modules/picamera/array.html#PiBayerArray    
    _header = BroadcomRawHeader.from_buffer_copy(
            data[176:176 + ct.sizeof(BroadcomRawHeader)])
            
    # uncomment for debug
    #print 'name',_header.name  
    #print 'bayer_order',_header.bayer_order
    #print 'bayer_format',_header.bayer_format
    
    # get the raw data as np.array
    data = data[32768:]
    data = np.fromstring(data, dtype=np.uint8)
    data = data.reshape((1952, 3264))[:1944, :3240]
        
    # promote data array to 16 bits, create space for
    # last two bits
    data = data.astype(np.uint16) << 2

    # now convert to the real 10 bit camera signal
    for byte in range(4):
        data[:, byte::5] |= ((data[:, 4::5] >> ((4 - byte) * 2)) & 0b11)
        
    # delete unused pixels  
    data = np.delete(data, np.s_[4::5], 1)

    # we get the data as [y,x], need it as [x,y] -> transposing helps
    # (1944L, 2592L) -> (1944L, 2592L)
    data = data.transpose()
    
    # now using only half of resolution to avoid demosaicing
    # small offsets of G1/G2-color channels will be only visible
    # at pixel sized display scales, not relevant for our purposes
    cplane = np.zeros((data.shape[0]/2,data.shape[1]/2,4), dtype=data.dtype)

    # sample into color planes

    # Attention! Bayer pattern seems to be different for v1/v2 cams
    # this works (as well as some code above) only for v1-cams
    
    # Note: Red         - Ch 0
    #       Gr (Green1) - Ch 1
    #       Gb (Green2) - Ch 2
    #       Blue        - Ch 3

    # type 0: 
    # hflip = False 
    # vflip = True
    if   _header.bayer_order==0 :
        cplane[:,:, 0] = data[0::2, 0::2] # Red
        cplane[:,:, 1] = data[0::2, 1::2] # Green1            
        cplane[:,:, 2] = data[1::2, 0::2] # Green2             
        cplane[:,:, 3] = data[1::2, 1::2] # Blue

    # type 1: 
    # hflip = False 
    # vflip = False            
    elif _header.bayer_order==1 :
        cplane[:,:, 1] = data[0::2, 0::2] # Green1            
        cplane[:,:, 0] = data[0::2, 1::2] # Red
        cplane[:,:, 3] = data[1::2, 0::2] # Blue
        cplane[:,:, 2] = data[1::2, 1::2] # Green2

    # type 2: 
    # hflip = True 
    # vflip = False 
    elif _header.bayer_order==2 :
        cplane[:,:, 3] = data[0::2, 0::2] # Blue
        cplane[:,:, 2] = data[0::2, 1::2] # Green2            
        cplane[:,:, 1] = data[1::2, 0::2] # Green1 
        cplane[:,:, 0] = data[1::2, 1::2] # Red
        
    # type 3: 
    # hflip = True 
    # vflip = True
    elif _header.bayer_order==3 :
        cplane[:,:, 2] = data[0::2, 0::2] # Green2
        cplane[:,:, 3] = data[0::2, 1::2] # Blue            
        cplane[:,:, 0] = data[1::2, 0::2] # Red        
        cplane[:,:, 1] = data[1::2, 1::2] # Green1

    else:
        print 'Unknown Bayer-pattern:',_header.bayer_order

    return cplane, _header.bayer_order

# this calculates the lens compensation table    
# it takes care of the changing table origin with
# respect to the raw image as well as the
# different directions the x- and y-coords of the
# table need to run in order to compensate a
# raw image with a specific orientation (hflip/vflip)
def calc_table(img,bayerType,equalize):
    
    # First pad the image to the right size - it took 
    # me quite a while to understand the mapping between 
    # raw images of different orientations and lens compensation table.
    # basically, the original raw image is enlarged to a size that 
    # 64x64 tiles can map directly into
    dx    = (img.shape[0]/32+1)*32
    dy    = (img.shape[1]/32+1)*32
    
    # now enlarging to "correct" size, converting to float 
    # for better precision during computations.
    pad_x =  dx-img.shape[0]
    pad_y =  dy-img.shape[1]
    
    # as the origin of the table relative to the raw image shifts,
    # depending on the hflip and vflip settings. We use the 
    # recorded bayerType (which reflects these settings) to 
    # pad and shift the image to the correct place 
    # for the rest of the computations
    
    
    # type 0: 
    # hflip = False 
    # vflip = True
    if   bayerType==0:
        tmpI = cv2.copyMakeBorder(img,pad_x,0,0,pad_y,cv2.BORDER_REPLICATE).astype(float)  
        
    # type 1: 
    # hflip = False 
    # vflip = False
    elif bayerType==1:
        tmpI = cv2.copyMakeBorder(img,pad_x,0,pad_y,0,cv2.BORDER_REPLICATE).astype(float)         
        
    # type 2: 
    # hflip = True 
    # vflip = False 
    elif bayerType==2:
        tmpI = cv2.copyMakeBorder(img,0,pad_x,pad_y,0,cv2.BORDER_REPLICATE).astype(float)
        
    # type 3: 
    # hflip = True 
    # vflip = True
    elif bayerType==3:
        tmpI = cv2.copyMakeBorder(img,0,pad_x,0,pad_y,cv2.BORDER_REPLICATE).astype(float)
        
    else:
        print 'Unknown Bayer-pattern:',_header.bayer_order  
        
    # ... downsizing with averaging. It is important here 
    # to do this iteratively in order to avoid scaling
    # artefacts. Also, the iterative down-sizing basically 
    # gets rid of all of the noise in the raw image 
    # - important if you want to have a reliable lens compensation
    while tmpI.shape[1]>img.shape[1]/16:
        dx = tmpI.shape[1]/2
        dy = tmpI.shape[0]/2            
        tmpI = cv2.resize(tmpI,(dx,dy),interpolation = cv2.INTER_AREA)
    raw = tmpI

    # find the maximum value in each channel in order
    # to make sure that the gains requested by the table
    # are always larger than one. This is important
    # as otherwise, weird things are happening (the 
    # lens-shading correction assumes that all values in the table are 
    # larger than 32)
    rawMax = np.amax(np.amax(raw, axis=0),axis=0)       
    if equalize:
        rmax = rawMax.max()
        rawMax[0] = rawMax[1] = rawMax[2] = rawMax[3] = rmax        
        
    # now follows a fast way to the compute lens compensation table

    # Note: if you are using below a larger scaler, 
    # say 64 for example, you will get a sensitivity 
    # boost. Of course, the noise floor
    # is multiplied as well, so it's a 
    # mixed blessing... 
    scaler = 32
    
    # array divide, ignoring zero entries....
    table = scaler*np.divide(rawMax,raw,where=raw!=0)

    # now we map the table (which is float) to
    # table we can use as lens compensation table
    # we first get the axis right (the picamera-library
    # wants first index: color channel, second 
    # index y-coord and third index y-coord), than 
    # we clip to the range allowable with uint8 (that
    # limits the maximal boost to 8x) and than we 
    # convert to uint8:
    table  = table.transpose(2,1,0).clip(0x00,0xff).astype(np.uint8).copy()

    # finally, we need to take care of the orientation
    # of the raw image to end up with a correctly 
    # oriented lens compensation table (comment: 
    # could have been done in the raw-conversion 
    # routine above, but here it is faster)
    if bayerType==1:
        print 'Modifying table for type 1!'
        table[0,:,:] = table[0,::-1,::-1]
        table[1,:,:] = table[1,::-1,::-1]
        table[2,:,:] = table[2,::-1,::-1]
        table[3,:,:] = table[3,::-1,::-1]
    elif bayerType==2:         
        print 'Modifying table for type 2!'
        table[0,:,:] = table[0,::-1,:]
        table[1,:,:] = table[1,::-1,:]
        table[2,:,:] = table[2,::-1,:]
        table[3,:,:] = table[3,::-1,:]   
    elif bayerType==0:         
        print 'Modifying table for type 0!'
        table[0,:,:] = table[0,:,::-1]
        table[1,:,:] = table[1,:,::-1]
        table[2,:,:] = table[2,:,::-1]
        table[3,:,:] = table[3,:,::-1]
    else:
        print 'Table ok for type 3'

    return table     
        
# simple routine for saving the calculated
# lens compensation table in human-readable
# form. In fact, it is the .h-format the 
# C-program for lens shading correction is
# expecting as input at compilation time
def save_table(filename,table):
    # the ls_table.h has the following sequence of channels
    cComments = ["R",
                "Gr",
                "Gb",
                "B"]

    # now write the table...
    with open(filename,'w') as file:

        # initial part of the table
        file.write("uint8_t ls_grid[] = {\n")

        for c in range(0,4):
            # insert channel comment (for readability)
            file.write("//%s - Ch %d\n"%(cComments[c],3-c))
            # scan the table
            for y in range(0,table.shape[1]):
                for x in range(0,table.shape[2]-1):         
                    file.write("%d, "%table[c][y][x])
                
                # finish a single line
                file.write("%d,\n"%table[c][y][table.shape[2]-1])
            
        # finish the the ls_grid array
        file.write("};\n");

        # write some additional vars which are expected in ls_table.h
        file.write("uint32_t ref_transform = 3;\n");
        file.write("uint32_t grid_width = %u;\n"%table.shape[1]);
        file.write("uint32_t grid_height = %u;\n"%table.shape[2]);    
    
# reading in a lens shading table previously stored
# as a .h-file. 
def read_table(inFile):
    
    # q&d-way to read in ls_table.h
    ls_table = []
    channel  = []

    with open(inFile) as file:       

        for line in file:
            # we skip the unimportant stuff
            if not (   line.startswith("uint") \
                    or line.startswith("}")):

                # the comments separate the color planes
                if line.startswith("//"):                
                    channel = []
                    ls_table.append(channel)
 
                else:
                    # scan in a single line
                    line = line.replace(',','')
                    lineData = [int(x) for x in string.split(line,' ')]
                    channel.append(lineData)

    return np.array(ls_table,dtype=np.uint8)    
    
    
# creating a test table
# note that the first spatial coord is y and the second is x
# we use this scheme here to match table format used in picamera
# Color channels are defined as follows:
# Red         - Ch 0
# Green1 (Gr) - Ch 1
# Green2 (Gb) - Ch 2
# Blue        - Ch 3
#
def create_testTable():
    table = np.zeros( (4,31,41) )
    dark   = 0x20
    bright = 0x20+0x40
    #bright = 0xff
 
    # colored border
    delta = 2
    for c in range(0,table.shape[0]):
        for y in range(0,table.shape[1]):
                for x in range(0,table.shape[2]):                        
                    if y==delta:
                        if c==0:
                            table[c][y][x] = bright
                        else:
                            table[c][y][x] = dark                        
                    elif x==delta:
                        if c==1:
                            table[c][y][x] = bright
                        else:
                            table[c][y][x] = dark                                 
                    elif x==table.shape[2]-1-delta:
                        if c==2:
                            table[c][y][x] = bright
                        else:
                            table[c][y][x] = dark
                    elif y==table.shape[1]-1-delta:
                        if c==3:
                            table[c][y][x] = bright
                        else:
                            table[c][y][x] = dark                    
                    else:
                        table[c][y][x] = dark                           
                    
    for xy in range(0,16):
        for c in range(0,table.shape[0]):
            table[c][0+xy][0+xy]                                 = bright
            table[c][0+xy][table.shape[2]-1-xy]                  = bright
            table[c][table.shape[1]-1-xy][0+xy]                  = bright        
            table[c][table.shape[1]-1-xy][table.shape[2]-1-xy]   = bright 
            
    # darker connector with spacers
    distance = 1
    for x in range(15,table.shape[2]-15):
        distance +=1
        for c in range(0,table.shape[0]):
            table[c][table.shape[1]-16][x] = (dark+bright)/2
            # distance test
            table[c][table.shape[1]-16+distance][x] = bright
            table[c][table.shape[1]-16-distance][x] = bright
            
    # white border
    for x in range(0,table.shape[2]):
        for c in range(0,table.shape[0]):
            table[c][0][x]                  = bright
            table[c][table.shape[1]-1][x]   = bright     
    for y in range(0,table.shape[1]):
        for c in range(0,table.shape[0]):        
            table[c][y][0]                  = bright
            table[c][y][table.shape[2]-1]   = bright             
                     
    return table.astype(np.uint8)
    
    
####### here the fun part starts! #####################################    

####### Settings ##################

# use testpattern or calculate lens compensation table
calcComp  = True
cam_mode  = 4

# whitebalance with lens compensation
equalize  = False

# use pre-stored lens compensation table
useStored  = False
storedName = 'ls_table.h'

# list of 
tasks = [ (False,False), (False, True), (True,False), (True,True) ]

###################################

# first creating the 
table = create_testTable()
print 'Created test table with',table.shape,table.dtype
    
for task in tasks:
    hflip, vflip = task
    print 'task:',hflip,vflip
    
    if   hflip==True and vflip==True:
        fileType = 'B3'
    elif hflip==False and vflip==True: 
        fileType = 'B0' 
    elif hflip==True and vflip==False: 
        fileType = 'B2'
    else:
        fileType = 'B1'
        
    tableName = 'table_'+fileType+'.h'
    rawName   = 'raw_'+fileType+'.jpg'
    
    # do we calculate compensation table?
    if calcComp:
        # yes, we do calculate a compensation table ...
        # So: first aquiring a raw reference image
        
        # we use a stream for data handling
        stream = io.BytesIO()    
        
        # capturing the reference image
        with PiCamera() as camera:
        
            # need to make sure that we are in the 
            # appropriate mode (the raw-routine assumes
            # that a full resolution image is supplied)
            camera.sensor_mode  = 2
        
            # setting the camera transformations 
            # as requested
            camera.hflip = hflip
            camera.vflip = vflip 
            
            # we want the camera to compute the whitebalance
            camera.awb_mode  = 'auto' 
            
            # Let the camera warm up for a couple of seconds
            print 'Capturing raw reference. Wait a few sec...'
            sleep(2)        
            
            # saving the color balance for later
            # uncomment this if you want to used 
            # autowhitebalance when taking the compensated
            # images for checking the compensation
#            awb_gains = camera.awb_gains
            
            # getting the raw data
            camera.capture(stream, format='jpeg', bayer=True)
            
            print 'Captured in camera mode:',camera.sensor_mode
            
            # rewinding the stream
            stream.seek(0)
            # ... and decoding into color planes
            cplane, bayerType = readRaw(stream.getvalue()[-6404096:])            
            # writing out the original raw capture, just for reference
            stream.seek(0)
            with open(rawName,'wb') as file:
                file.write(stream.getvalue())
            
        # now calculating the compensation table
        print 'Calculating table for bayerType',bayerType
        table = calc_table(cplane,bayerType,equalize)
        
        print 'Calculated table',table.shape,table.dtype
            
        print 'Saving table as',tableName     
        save_table(tableName,table)    
    else:
        # we work with a precalculated standard table
        if useStored:
            table = read_table(storedName)
        else:
            table = create_testTable()
    
    # now testing the lens compensation table
    with PiCamera(lens_shading_table=table) as camera:

        # Setting camera resolution
        camera.resolution = (800,600)

        # trying out different modes...
        camera.sensor_mode  = cam_mode
        
        # setting again the camera mapping
        camera.hflip = hflip
        camera.vflip = vflip
        
        # did we store the color balance?
        # if so, restore it 
        if 'awb_gains' in locals():
            print 'Setting color balance',awb_gains
            camera.awb_mode  = 'off'    
            camera.awb_gains =  awb_gains 
        else:
            print 'Using Auto Whitebalance!'
            camera.awb_mode = 'auto'
                    
        # Let the camera warm up for a couple of seconds
        # to get the exposure right
        print 'Capturing raw reference. Wait a sec...'
        sleep(2)
        
        # Capturing the compensated image
        camera.capture('x_'+rawName, format='jpeg')         
        print 'Captured in camera mode:',camera.sensor_mode        
        
        # uncomment the following line if you want the 
        # raw image of this capture as well
        #camera.capture('x_'+rawName, format='jpeg', bayer=True)     
        
print
print '... done.'
