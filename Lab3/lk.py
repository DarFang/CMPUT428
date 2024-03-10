import os
import sys
import cv2
import numpy as np
import math
import time


def readTrackingData(filename):
    if not os.path.isfile(filename):
        print("Tracking data file not found:\n ", filename)
        sys.exit()

    data_file = open(filename, 'r')
    lines = data_file.readlines()
    no_of_lines = len(lines)
    data_array = np.zeros((no_of_lines, 8))
    line_id = 0
    for line in lines:
        words = line.split()[1:]
        if len(words) != 8:
            msg = "Invalid formatting on line %d" % line_id + " in file %s" % filename + ":\n%s" % line
            raise SyntaxError(msg)
        coordinates = []
        for word in words:
            coordinates.append(float(word))
        data_array[line_id, :] = coordinates
        line_id += 1
    data_file.close()
    return data_array


def writeCorners(file_id, corners):
    # write the given corners to the file
    corner_str = ''
    for i in range(4):
        corner_str = corner_str + '{:5.2f}\t{:5.2f}\t'.format(corners[0, i], corners[1, i])
    file_id.write(corner_str + '\n')


def drawRegion(img, corners, color, thickness=1):
    # draw the bounding box specified by the given corners
    for i in range(4):
        p1 = (int(corners[0, i]), int(corners[1, i]))
        p2 = (int(corners[0, (i + 1) % 4]), int(corners[1, (i + 1) % 4]))
        cv2.line(img, p1, p2, color, thickness)


def initTracker(img, corners):
    # initialize your tracker with the first frame from the sequence and
    # the corresponding corners from the ground truth
    # this function does not return anything
    global old_frame
    global p0
    old_frame = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    p0 = corners.T.astype(np.float32)
    pass


def updateTracker(img):
    # update your tracker with the current image and return the current corners
    # at present it simply returns the actual corners with an offset so that
    # a valid value is returned for the code to run without errors
    # this is only for demonstration purpose and your code must NOT use actual corners in any way
    global old_frame
    global p0
    frame_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # parameters for lucas kanade optical flow
    lk_params = dict( winSize  = (32,32),
                  maxLevel = 8,
                  criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 9, 0.02555))
    p1, st, err = cv2.calcOpticalFlowPyrLK(old_frame, frame_img, p0, None, **lk_params)
    old_frame = frame_img.copy()
    p0 = p1.copy()

    return p1.T


if __name__ == '__main__':
    sequences = ['box']
    seq_id = 0

    write_stats_to_file = 0
    show_tracking_output = 1

    arg_id = 1
    if len(sys.argv) > arg_id:
        seq_id = int(sys.argv[arg_id])
        arg_id += 1
    if len(sys.argv) > arg_id:
        write_stats_to_file = int(sys.argv[arg_id])
        arg_id += 1
    if len(sys.argv) > arg_id:
        show_tracking_output = int(sys.argv[arg_id])
        arg_id += 1

    if seq_id >= len(sequences):
        print('Invalid dataset_id: ', seq_id)
        sys.exit()

    seq_name = sequences[seq_id]
    print('seq_id: ', seq_id)
    print('seq_name: ', seq_name)

    src_fname = seq_name + '/frame%05d.jpg'
    ground_truth_fname = seq_name + '.txt'
    result_fname = seq_name + '_res.txt'

    result_file = open(result_fname, 'w')

    cap = cv2.VideoCapture()
    if not cap.open(src_fname):
        print('The video file ', src_fname, ' could not be opened')
        sys.exit()

    # thickness of the bounding box lines drawn on the image
    thickness = 2
    # ground truth location drawn in green
    ground_truth_color = (0, 255, 0)
    # tracker location drawn in red
    result_color = (0, 0, 255)

    # read the ground truth
    ground_truth = readTrackingData(ground_truth_fname)
    no_of_frames = ground_truth.shape[0]


    print('no_of_frames: ', no_of_frames)

    ret, init_img = cap.read()
    if not ret:
        print("Initial frame could not be read")
        sys.exit(0)

    # extract the true corners in the first frame and place them into a 2x4 array
    init_corners = [ground_truth[0, 0:2].tolist(),
                    ground_truth[0, 2:4].tolist(),
                    ground_truth[0, 4:6].tolist(),
                    ground_truth[0, 6:8].tolist()]
    init_corners = np.array(init_corners).T
    # write the initial corners to the result file
    writeCorners(result_file, init_corners)

    # initialize tracker with the first frame and the initial corners
    initTracker(init_img, init_corners)

    if show_tracking_output:
        # window for displaying the tracking result
        window_name = 'Tracking Result'
        cv2.namedWindow(window_name)

    # lists for accumulating the tracking error and fps for all the frames
    tracking_errors = []
    tracking_fps = []

    for frame_id in range(1, no_of_frames):
        ret, src_img = cap.read()
        if not ret:
            print("Frame ", frame_id, " could not be read")
            break
        actual_corners = [ground_truth[frame_id, 0:2].tolist(),
                          ground_truth[frame_id, 2:4].tolist(),
                          ground_truth[frame_id, 4:6].tolist(),
                          ground_truth[frame_id, 6:8].tolist()]
        actual_corners = np.array(actual_corners).T

        start_time = time.process_time()
        # update the tracker with the current frame
        tracker_corners = updateTracker(src_img)
        end_time = time.process_time()

        # write the current tracker location to the result text file
        writeCorners(result_file, tracker_corners)

        # compute the tracking fps
        current_fps = 1.0 / (end_time - start_time)
        tracking_fps.append(current_fps)

        # compute the tracking error
        current_error = math.sqrt(np.sum(np.square(actual_corners - tracker_corners)) / 4)
        tracking_errors.append(current_error)

        if show_tracking_output:
            # draw the ground truth location
            drawRegion(src_img, actual_corners, ground_truth_color, thickness)
            # draw the tracker location
            drawRegion(src_img, tracker_corners, result_color, thickness)
            # write statistics (error and fps) to the image
            cv2.putText(src_img, "{:5.2f} {:5.2f}".format(current_fps, current_error), (5, 15), cv2.FONT_HERSHEY_COMPLEX_SMALL, 1, (255, 255, 255))
            # display the image
            cv2.imshow(window_name, src_img)

            if cv2.waitKey(1) == 27:
                break
                # print 'curr_error: ', curr_error

    mean_error = np.mean(tracking_errors)
    mean_fps = np.mean(tracking_fps)

    print('mean_error: ', mean_error)
    print('mean_fps: ', mean_fps)

    result_file.close()

    if write_stats_to_file:
        fout = open("tracking_stats.txt", "a")
        fout.write('{:s}\t{:d}\t{:12.6f}\t{:12.6f}\n'.format(sys.argv[0], seq_id, mean_error, mean_fps))
        fout.close()
