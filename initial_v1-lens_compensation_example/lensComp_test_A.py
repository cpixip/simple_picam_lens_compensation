# for stream handling
import io

# for delays
from time import sleep

# need picamera in rwb27 version
# https://github.com/waveform80/picamera/pull/470#issuecomment-433642918
from picamera import PiCamera

# for computations
import cv2
import numpy as np

# delay for autofcts to get a decent frame
wait_delay = 3

# reading the raw data from a .jpg-stream
# derived from picamera 1.13 documentation
# https://github.com/waveform80/picamera/
# Important: only verified for v1-cams with
# camera.hflip = True
# camera.vflip = True
# (see below when raw image is actually taken)
def readRaw(data):

    # check again for header
    assert data[:4] == 'BRCM'

    # extract raw data
    data = data[32768:]
    data = np.fromstring(data, dtype=np.uint8)

    # reshape the data and strip off the unused bytes
    data = data.reshape((1952, 3264))[:1944, :3240]
        
    # promote data array to 16 bits, create space for
    # last two bits
    data = data.astype(np.uint16) << 2

    # now convert to real 10 bit camera signal
    for byte in range(4):
        data[:, byte::5] |= ((data[:, 4::5] >> ((4 - byte) * 2)) & 0b11)
        
    # delete unused pixels  
    data = np.delete(data, np.s_[4::5], 1)

    # using only half of resolution to avoid demosaicing
    # small offsets of color channels will be only visible
    # at pixel sized display scales
    cplane = np.zeros((data.shape[0]/2,data.shape[1]/2,4), dtype=data.dtype)

    # sample into color planes (hflip=true,vflip=true)
    # the code below is wrong if hflip and vflip are not set!
    cplane[:,:, 3] = data[1::2, 0::2] # Red        
    cplane[:,:, 2] = data[1::2, 1::2] # Green1
    cplane[:,:, 1] = data[0::2, 0::2] # Green2 
    cplane[:,:, 0] = data[0::2, 1::2] # Blue    
      
    return cplane
    
# calculating a lens shading correction from a raw image
# works currently only with images where both hflip and vflip are 
# set to true. (However, works for both v1- and v2-cams)
def calc_table(img):
    
    # padding the image to the right size - it took me quite a while to understand
    # the mapping between raw image and lens compensation table
    # basically, it's padded to a size that 32x32 tiles can map directly
    dx    = (img.shape[0]/32+1)*32
    dy    = (img.shape[1]/32+1)*32
    
    # now enlarging to "correct" size, convert to float for better precision
    pad_x =  dx-img.shape[0]
    pad_y =  dy-img.shape[1]
    tmpI = cv2.copyMakeBorder(img,0,pad_x,0,pad_y,cv2.BORDER_REPLICATE).astype(float)
    
    # ... downsizing with averaging. It is important to do this iteratively in order
    # to avoid artefacts. Also, the iterative down-sizing gets rid of all of the noise
    # in the raw image - important if you want to have a reliable lens compensation
    while tmpI.shape[1]>img.shape[1]/16:
        dx = tmpI.shape[1]/2
        dy = tmpI.shape[0]/2            
        tmpI = cv2.resize(tmpI,(dx,dy),interpolation = cv2.INTER_AREA)
    raw = tmpI

    # get the maximum value in each channel in order
    # to make sure that gains requested by the table
    # are always larger than one. This is important
    # as otherwise, weird things are happening (the 
    # lens-shading correction assumes that all values in the table are 
    # larger than 32)
    rawMax = np.amax(np.amax(raw, axis=0),axis=0)       
        
    # probaly the fastest way to compute lens compensation

    # Note: if you use a larger scaler, say 64 for example
    # you will get a sensitivity boost. Of course, the noise floor
    # is multiplied as well, so it's a mixed blessing... 
    scaler = 32
    # array divide, ignoring zero entries....
    table = scaler*np.divide(rawMax,raw,where=raw!=0)
    
    # convert back to int, project values into safe range, get the 
    # axis of the array in the right order to feed to the camera
    return table.transpose(2,0,1).clip(0x00,0xff).astype(np.uint8)

    
# simple output routine to dump the lens compensation table
# into a human readable form. Is the same as the ls_table.h-file
# which is used in the c-prg for lens shading
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
    
# reading in a lens shading table previously written to disk
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
    
####### here the fun part starts! #####################################    
# Lens shading compensation consists of the following steps:
# 0) aim the camera at an even lid surface
# 1) capture a raw image from the camera
# 2) calculate lens shading correction
# 3) capture an image with the calculated lens shading correction
# 5) compare the two images ('raw_original.jpg' and 'with_lensCompensation.jpg')
#######################################################################


# 1) capturing the raw frame

# we use a stream for data handling in the raw capture
stream = io.BytesIO()

with PiCamera() as camera:
    # this is important! the code currently only 
    # works with the image mirrored both horizontally
    # and vertically! 
    camera.hflip = True
    camera.vflip = True
    camera.awb_mode  = 'auto'
    # Let the camera warm up for a couple of seconds
    print 'Capturing raw reference. Wait a few sec...'
    sleep(wait_delay)
    awb_gains = camera.awb_gains
    # Capture the image, including the Bayer data
    camera.capture(stream, format='jpeg', bayer=True)
    
    # rewind the stream
    stream.seek(0)
    
    # read the whole buffer (well, almost)
    # and convert it to the cv2-format we are using
    cplane = readRaw(stream.getvalue()[-6404096:])
    
    # just for debug information - normally commented out
    print 'Got data with dims:',cplane.shape,' with',cplane.dtype    
    print 'Max red:',cplane[:,:,0].max()
    print 'Max green1:',cplane[:,:,1].max()
    print 'Max green2:',cplane[:,:,2].max()
    print 'Max blue:',cplane[:,:,3].max()    
    
    # just for fun, writing out the different color planes
    cv2.imwrite('raw_red.jpg',cplane[:,:,0])
    cv2.imwrite('raw_green1.jpg',cplane[:,:,1])
    cv2.imwrite('raw_green2.jpg',cplane[:,:,2])
    cv2.imwrite('raw_blue.jpg',cplane[:,:,3])    
    
    # writing out the original raw capture, just for reference
    # with a lens different from the standard lens, there should
    # be color as well as intensity variations noticable across 
    # the image frame
    stream.seek(0)
    with open('raw_original.jpg','wb') as file:
        file.write(stream.getvalue())

# 2) calculate the lens shading correction
print 'Calculation compensation table...'
lensShadingCompensation = calc_table(cplane)
print 'Calculated lens shading compensation table with size',lensShadingCompensation.shape,lensShadingCompensation.dtype

# ... and save it as c-include file
print 'Saving lens shading compensation as .h-file'
save_table('myLensShading.h',lensShadingCompensation)

# set this to True if you want to use a stored lens compensation table
if False:
    print 'Reading lens compensation from .h-file'
    lensShadingCompensation = read_table('myLensShading.h')
    print 'Read lens shading compensation table with size',lensShadingCompensation.shape,lensShadingCompensation.dtype

# 3) try out the calculated lens shading
print 'Grabbing image with lens shading compensation'
with PiCamera(lens_shading_table=lensShadingCompensation) as camera:
    # using here the same hflip and vflip settings as above,
    # to make both images written to disk comparable.
    # In principle, at this point of the story, it does
    # not matter what value these variables are
    camera.hflip = True
    camera.vflip = True
    camera.awb_mode  = 'off'    
    camera.awb_gains =  awb_gains 
    
    sleep(wait_delay)
    camera.capture('with_lensCompensation.jpg')

# that's it:
print '... done.'
