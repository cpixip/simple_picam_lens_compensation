- this is the second version of a script calculating a lens compensation table for v1-cameras.

**New**: this script takes into account the different geometric mapping induced by the various `hflip`- and `vflip`-parameters. Different `hflip`- and `vflip`-parameters change the Bayer-pattern as well as the position of the origin of the raw image.

Also, the scrip now makes clear that the raw image used for calibration needs to be taken in `camera.sensor_mode = 2`. 

It writes out various raw images, lens compensation tables and compensated test images (labeld according to the Bayer-pattern used, "B0/B1/B2/B3"). 

Bascially, all these images should be the same (i.e., there should be only minor difference for example between a table labeled with "B0" and a table labeled with "B1").

Any of the calculated tables should work with any of the `sensor_modes` of the camera in later captures - however, only a few modes have actually been tested. Any feedback is appreciated!
