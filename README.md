# Picamera lens compensation for v1-cameras

In this repository I collect an evolving selection of scripts which are aiming at calculating a valid lens compensation table for v1-cameras. The scripts include a lot of comments, so be sure to read the fine details.

## Background

### Standard Cameras

The standard cameras attached to the Raspberry Pi use lens shading compensation tables specific to the standard lens attached. Currently, there are two variants available, the v1-camera based ('OV5647') and the new and higher resolution v2-camera ('IMX219') and there is appropriate support for these cameras in the firmware.

### The curse of microlenses
Both v1- and v2-cameras do not feature a plain sensor array, but there is an array of microlenses above the normal sensor array. These microlenses improve the performance compared to a simple sensor array, especially with the short focal lengths used in the v1- and v2-camera (these cameras were derived from mobile hardware). Specifically, they optically "turn" the viewline of the outer pixels towards the center of the lens, increasing the sensitivity of these pixels.

To function properly, the microlens array needs to be designed for the lens attached. Specifically, the pitch of the microlens array is slightly less than the pitch of the sensor array, thus "aiming" the view of pixels located in the outer regions of the sensor toward the center of the lens attached. In this way, microlens arrays improve the vignetting effects of the simple optics of the standard lens. The remaining corrections are actually done by the lens shading compensation.

For special applications it is necessary to detach the standard lens and put a different lens in front of the sensor. Most of the time, the optical pathway dramatically changes with a lens change. For example, in my application, I use a Schneider Componon-S lens with 50 mm focal length, compared to the standard of about 4 mmm. Simply speaking, in such a case the microlens array does no longer "aim" the outer pixels correctly toward the lens. More important, the light entering a single RGB-pixel is misaligned, and in the outer regions of the sensor light which for example passed through the red filter will fall on neighbouring pixels sensitive to green or blue. The effect of this color spill will be noticable as a drop in color saturation towards the outer regions of the image.

#### v2-cameras are impractical for lens hacks
Experiments have shown that the mismatch created by attaching a lens with a different focal length is remarkably different for v1- and v2-camera sensors. While the v1-camera barely shows any color desaturation towards the edges, the effect is quite noticable
for v2-camera sensor.

The problem is: lens compensation algorithm available in the Raspberry pipeline can **not** compensate for such  color desaturations. We would need a much more complicated algorithm. 

Now, the described effect of desaturation is relatively small on the old v1-sensor. It is however very noticable on the newer v2-sensor - only the center part of the image of a v2-sensor is such that it can be compensated to a flat response with the available lens shading compensation. In the end, the larger v2-sensor gives us back a smaller usable resolution than the smaller v1-sensor. That is the reason the code in this repository does not handle v2-sensors.

### Usage examples and hints
#### Normal lens compensation procedure
The lens compensation works in two steps. First, you point the camera towards a homogenous surface and take a raw image. The raw image is than used to calculate a lens compensation table which you can store in human-readable form on the disk. In your actual application, you would read in the precalculated table and use it to capture your images.

An important aspect of this process is that the initial homogenous surface is really homogenous in light intensity over the whole area the raw calibration image is taken. You can image a spotless white paper. I am using an old Kodak gray card for this purpose. Make sure that the illumination is even across the whole imaging area. Also, take into account that lamps tend to vary in intensity with the frequency of AC-power. Make sure that you do not pick up possible fast illumination changes caused by this, for example by using exposure times longer than 1/10 of a second. 

Another important thing is to make sure that all four channels of the raw image are equally well exposed. This is no issue in normal daylight, but with artifical illumination the blue color channel tends to become noisy. This will effect the quality of the lens compensation table. One good starting point for experiments is a plain white paper placed in the open on a day with clouded skys. In my setup, I am using a 3D-printed integration sphere as homogenous reference surface.

#### Limits of lens compensation
##### Scaling limits
The way the lens shading compensation is implemented in the Raspberry Pi limits the available scaling factors from 1.0 ("32" in the .h-file table) to about 8.0 (255 in the .h-file). This is more than enough for the usual lens compensation, but it is important to realize these limits if you want to experiment with more exotic usages. Do never go below scaling factors of 1.0 ("32") - using such values is undefined. It seems that some values work, some others don't. So just don't use them.

##### Resolution of the table
The lens compensation table has a rather low resolution. This means that small dirt particels on the sensor can **not** be compensated electronically. You have to clean the sensor by hand to remove these speckles.

##### Implementation of the lens shading compensation
Basically, you do not have access to the compuational block which does the lens shading. So you have to live with what's available. Compared to a properly implementation, and possibly due to the limited resources available on the Raspberry Pi, the lens compensation table is not properly scaled up to the full image resolution. This results in a somewhat blocky appearance of the results, compared to a proper implementation. Also, there might be some small blue or yellow/orange lines visible at the extreme border of the image when lens compensation is used (a few pixels wide) - probably an implementation issue.

#### Exotic usages of lens compensation
##### "Improvement" of camera sensitivity
Basically, any entry in the lens compensation table with value "32" results in the multiplication of the relevant pixels by a factor of 1.0. If you scale (look at the scripts!) the table not by "32" but by "64", you double the sensitivity of the sensor. Or, in other words, the digital gain factor is increase by two. Or, in yet other words, the ISO-value is doubled. Of course, the noise floor is also increase by the same amount. You can counteract this by taking rapidly several images and average them. From my experience, about 4 images give you a nice image with improved sensitivity.

##### Semi-HDR for security applications
Imagine you have a security camera application where part of the area the camera sees is in bright daylight but other parts are in the shadows. If you take a raw image of such a static scene and calculate a lens compensation table from that image, the areas in bright daylight will end with scalers around 1.0 while the areas in the shadows have scalers larger than one. If you run the camera now with the calculated lens compensation table, the shadows will be much better visible in the cameras image than before.
