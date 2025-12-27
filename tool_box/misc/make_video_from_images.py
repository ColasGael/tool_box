#!/usr/bin/env python

from argparse import ArgumentParser
import glob
import os
import subprocess

import cv2


def make_video_from_images(image_filenames, out_video_path, fps):
    # Get image dimension
    height, width, _ = cv2.imread(image_filenames[0]).shape

    # Overlay text parameters
    font = cv2.FONT_HERSHEY_SIMPLEX 
    org = (3096//3, 25) 
    fontScale = 1
    color = (0, 0, 255)  # BGR
    thickness = 2  # px

    video = cv2.VideoWriter(out_video_path, cv2.VideoWriter_fourcc(*'XVID'), fps, (width,height))
    for image_filename in image_filenames:
        overlay_text = os.path.basename(os.path.dirname(image_filename))
        img = cv2.imread(image_filename)
        img = cv2.putText(img, overlay_text, org, font, fontScale, color, thickness, cv2.LINE_AA) 
        video.write(img)
    cv2.destroyAllWindows()
    video.release()


def process_images(images_folder_paths, out_folder_path, out_video_filename, rate, fps, video_format):
    image_filenames = []
    for images_folder_path in images_folder_paths:
        image_filenames = image_filenames + list(sorted([os.path.join(images_folder_path, img) for img in os.listdir(images_folder_path) if (img.endswith(".png") or img.endswith(".jpg"))]))

    out_video_path = os.path.join(out_folder_path, out_video_filename)

    print("Processing {} images...".format(len(image_filenames)))
    if (video_format == "avi"):
         # Generate a Video
         make_video_from_images(image_filenames, out_video_path, fps)

    elif (video_format == "gif"):
        # Sample the frames
        image_filenames = [image_filename for i, image_filename in enumerate(image_filenames) if i % (int)(1./rate) == 0]
        # Get image dimension
        height, width, _ = cv2.imread(image_filenames[0]).shape
        # Generate a GIF
        cmd_generate_gif = "convert -delay 10 -loop 0 -layers optimize -resize {}x{} ".format(height//2, width//2) + " ".join(image_filenames) + " " + out_video_path 
        process = subprocess.Popen(cmd_generate_gif.split(), stdout=subprocess.PIPE)
        process.communicate()

    else:
        raise NotImplementedError

    print("Video generated in {} !".format(out_video_path))


def get_args():
    parser = ArgumentParser(description = "Make a video from a folder of images.")

    parser.add_argument('image_folder', 
                        type=str, 
                        help="Absolute path to the image folder.")
    parser.add_argument('-o', '--out_folder', 
                        type=str, 
                        default="~/temp",
                        help="Absolute path to the output folder.")
    parser.add_argument('-f', '--out_video_filename', 
                        type=str, 
                        default="", 
                        help="Filename of the generated video.")
    parser.add_argument('-r', '--rate', 
                        type=float, 
                        default=1., 
                        help="What rate of frames to keep.")    
    parser.add_argument('--fps', 
                        type=float, 
                        default=20, 
                        help="Frames per second.")
    parser.add_argument('--format', 
                        type=str, 
                        choices=["avi", "gif"],
                        default="avi", 
                        help="Video output format.")

    args = parser.parse_args()

    args.image_folder = os.path.expanduser(args.image_folder)
    args.out_folder = os.path.expanduser(args.out_folder)
    
    if not args.out_video_filename:
        args.out_video_filename = os.path.basename(os.path.normpath(args.image_folder))
    args.out_video_filename = "{}.{}".format(os.path.splitext(args.out_video_filename)[0], args.format)

    return args


def main():
    args = get_args()

    images_folder_paths = [images_folder for images_folder in sorted(glob.glob(args.image_folder)) if os.path.isdir(images_folder)]
    if not images_folder_paths:
        images_folder_paths = [args.image_folder]

    if not os.path.isdir(args.out_folder):
        os.mkdir(args.out_folder)

    process_images(images_folder_paths, args.out_folder, args.out_video_filename, args.rate, args.fps, args.format)


if __name__=="__main__":
    main()
    
