Kinect Halloween Skeleton
=========================

This is a hacked together script that displays a skeleton that tracks to your body and makes for a great installation in your front yard for halloween.

For my setup, I put together a large PVC screen frame with a queen size sheet, put the kinect in right front of it on a 1-foot tall box, and a projector behind it, and placed it all a few feet from the sidewalk in our driveway.  I used an extra long active USB 3 cable and HDMI cable I found on Amazon to reach the setup and keep my laptop indoors.  Didn't end up needing to power the active USB cable since the Kinect has its own power source.

I've only tested this with an old first-generation Kinect I dusted off when cleaning out my garage.

To setup:

* Use Ubuntu or a debian-based dist
* Run ./install-kinect-libs.sh
* Put any images you want to show when there is no user into the images-other/ folder
  * The images in there now are public domain, from pexels.com

To run:

./halloween-skeleton.py

The kinect driver crashes sometimes, so use run.sh to keep running it in a loop.

This doesn't work well on a multi-monitor setup, so make sure to turn off all but the main display when running.
