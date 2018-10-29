# Simple picamera lens compensation
Calculating and using the new lens compensation, implemeted by rwb27, with a v1-camera.

# Setup
You need to download and install the branch rwb27 created and which is discussed here: https://github.com/waveform80/picamera/pull/470#issuecomment-433642918

Point your Raspi-Cam (this script only works for v1-cameras!) at white or gray surface which should be imaged homogenously. If you have exchanged the standard lens with a different one, the image you will get will show color and intensity variations.

Next, run the script 'lensComp_test_A.py'. It will take first a raw image and than compute and write out a corresponding lens compensation table. After this, the newly calculated table will be used to capture a corrected image. The corrected image (stored on disk as 'with_lensCompensation.jpg' should show less color and intensity variation than the raw image (stored as 'raw_original.jpg'). Example images are available above.

# File Discriptions
lensComp_test_A.py: the script described above.

raw_original.jpg: an example image taken with the lens shading correction of the standard lens.

with_lensCompensation.jpg: the comparision image taken the newly calculated lens correction table.

myLensShading.h: the lens shading correction table written out as .h-file.

myLensShading.JPG: a visulation of the calculated table.

comparision.png: a comparision of the camera, without and with lens shading correction.

(for the curious: the images used in the example show a part of a film gate for a Super 8 film scanner and were taken with a v1-camera fitted with a Schneider Componon-S 50mm as lens)
