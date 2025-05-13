import cv2
import time
from picamera2 import Picamera2
import numpy as np

#rpicam-hello -t 0 --hdr off --ev 0.0 --shutter 20000 --gain 2.0 --metering spot --framerate 60

#rpicam-hello -t 0 --shutter 20000 --gain 2.0 --metering spot --framerate 60
#rpicam-hello -t 0 --shutter 20000 --gain 2.0 --framerate 60
# rpicam-hello -t 0 --framerate 60 --shutter 15000 --gain 2.0 --brightness 0.0 --contrast 1.0 --sharpness 0.0 --saturation 1.0 
# 728x544-YUV420 (1) 1456x1088-BGGR_PISP_COMP1

picam2 = Picamera2()

raw_width=728
raw_height=544

main_width=728
main_height=544

#picam2.configure(picam2.create_video_configuration(main={"format":'SRGGB10_CSI2P',"size":(width,height)}))

config = picam2.create_still_configuration(
    main={"size": (main_width,main_height)}, # scale down the image, but maintain the full field of view
    raw={'size': (raw_width, raw_height)},
    buffer_count=2,
    controls={'FrameRate': 60},
)
picam2.configure(config)
picam2.start()


# Background subtractor
# bg_subtractor = cv2.createBackgroundSubtractorMOG2()
 
# Current mode
mode = "threshold"
 
# FPS calculation
prev_time = time.time()

cut_0 = False
cut_1 = False
cut_2 = False

 
while True:
 #   ret, frame = capture.read()
    frame = picam2.capture_array()
#    if not ret:
#        break
 
    if cut_0:
        frame[:,:,2] = np.zeros([frame.shape[0], frame.shape[1]])
    
    if cut_1:
        frame[:,:,1] = np.zeros([frame.shape[0], frame.shape[1]])
    
    if cut_2:
        frame[:,:,0] = np.zeros([frame.shape[0], frame.shape[1]])


    #frame = cv2.flip(frame, 1)
    display_frame = frame.copy()
 
    if mode == "threshold":
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        _, display_frame = cv2.threshold(gray, 32, 255, cv2.THRESH_BINARY)
        display_frame = cv2.cvtColor(display_frame, cv2.COLOR_GRAY2BGR)
 
    elif mode == "edge":
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 100, 200)
        display_frame = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
 
    elif mode == "bg_sub":
        fg_mask = bg_subtractor.apply(frame)
        display_frame = cv2.bitwise_and(frame, frame, mask=fg_mask)
 
    elif mode == "contour":
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        display_frame = cv2.drawContours(frame.copy(), contours, -1, (0, 255, 0), 2)
 
    # Calculate actual processing FPS
    curr_time = time.time()
    processing_fps = 1 / (curr_time - prev_time)
    prev_time = curr_time
 
    # Display actual processing FPS
    cv2.putText(
        display_frame, f"FPS: {int(processing_fps)} Mode: {mode} 0:{cut_0} 1:{cut_1} 2:{cut_2}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1
    )
 
    # Show video
    cv2.imshow("Live Video", display_frame)
 
    key = cv2.waitKey(1) & 0xFF
    if key == ord("0"):
        cut_0 = not(cut_0)
    elif key == ord("1"):
        cut_1 = not(cut_1)
    elif key == ord("2"):
        cut_2 = not(cut_2)
    elif key == ord("t"):
        mode = "threshold"
    elif key == ord("e"):
        mode = "edge"
    elif key == ord("b"):
        mode = "bg_sub"
    elif key == ord("c"):
        mode = "contour"
    elif key == ord("n"):
        mode = "normal"
    elif key == ord("q"):
        break
 
# Clean up
capture.release()
cv2.destroyAllWindows()