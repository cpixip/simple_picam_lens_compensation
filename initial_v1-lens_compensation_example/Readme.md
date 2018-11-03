# First try...

In this directory you can find a simple script which creates a lens compensation table for v1-cameras attached to a Raspberry Pi. It can be used to replace the standard lens compensation of the Raspi-cam in case you have attached a different lens.

The script uses the picamera-library created by **waveform80**, as enhanced by **rwb27** ([see discussion here](https://github.com/waveform80/picamera/pull/470#issuecomment-435473974)). You need to install this branch before the scripts in this repository will work. Note that the bare picamera-library v 1.13 will not work.

The script in this folder works with the settings `camera.hflip = True` and `camera.vflip = True`. Implicitly (in the routine which decodes the raw image) it is also assumed that the `camera.mode = 0`. 

## Setup and Usage

You need to download and install the branch **rwb27** created and which is discussed here: [https://github.com/waveform80/picamera/pull/470#issuecomment-433642918]

Point your Raspi-Cam at sufficiently homogeneous white or gray surface. If you have exchanged the standard lens with a different lens, the image you will get will show most probably color and intensity variations from the center to the edge of the image. The reason is that the standard lens compensation table within the Raspi-software does not match the characteristics of the lens you have attached to the sensor.

The script `lensComp_test_A.py`will first take a raw image of the homogenous surface you are pointing the camera at and compute out of this a lens compensation table for your specific lens. This image is stored on disk as `raw_original.jpg` and should show some color and intensity variations.

Secondly, from the data of the raw image, a lens compensation table is computed and written out in human readable form in the file `myLensShading.h`. You can read back and use this file in your own application. It should match the format of the .h-file which is used in a modified [RaspiStill prg](https://www.raspberrypi.org/forums/viewtopic.php?f=43&t=190586). However, I have not tested this.

Thirdly, the new lens compensation table is checked. The picamera is initialized with the new table and an image stored to disk as `with_lensCompensation.jpg`. This image aquired with the new lens compensation table should show much less color or intensity variations compared to the `raw_original.jpg` aquired with the standard table.

