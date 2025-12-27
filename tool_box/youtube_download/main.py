#!/usr/bin/env python

import argparse
import os
import re
import subprocess

# import audio_metadata

# Assume it is saved in the same directory as this file
YT_DL_EXEC_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'youtube-dl')
DEFAULT_YT_DL_AUDIO_CONF = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'youtube-dl_audio.conf')
DEFAULT_YT_DL_VIDEO_CONF = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'youtube-dl_video.conf')

SEP_CHAR = '#'
DEFAULT_TEMPLATE = '%(title)s.%(ext)s'
# DEFAULT_AUDIO_DIR = "D:\\Documents\\Media\\music\\playlists"
DEFAULT_AUDIO_DIR = "/home/colasg/Downloads"
# DEFAULT_VIDEO_DIR = "D:\\_temp"
DEFAULT_VIDEO_DIR = "/home/colasg/Downloads"


def print_metadata(filepath):
    metadata = audio_metadata.load(filepath).get('tags', {})
    useful_metadata = {
		'artist': metadata.get('artist', 'NA'),
		'album': metadata.get('album', 'NA'),
		'title': metadata.get('title', 'NA'),
		'genre': metadata.get('genre', 'NA'),
    }
    print(useful_metadata)


def audiofiles_postprocessing(out_dir, filepaths):
    all_dir = [os.path.abspath(x[0]) for x in os.walk(out_dir)]

    new_filepaths = []
    for filepath in filepaths:
        out_dir, filename = os.path.split(filepath)
        artist = filename.split(SEP_CHAR)[0].replace('_', ' ')

        save_dir = next((dir for dir in all_dir if artist == os.path.basename(dir)), "")

        if len(save_dir) == 0:
            save_dir = os.path.join(out_dir, artist)
            print("Creating new artist directory: {}".format(save_dir))
            os.mkdir(save_dir)
            all_dir.append(save_dir)

        new_filepath = os.path.join(save_dir, filename.lower().replace('_', '-').replace(SEP_CHAR, '_'))

        if os.path.isfile(new_filepath):
            print("Audio file {} already exists.".format(new_filepath))
            print("Remove duplicate file {}.".format(filepath))
            os.remove(filepath)
            continue

        os.rename(filepath, new_filepath)
        new_filepaths.append(new_filepath)
        print(new_filepath)
        # print_metadata(new_filepath)

    return new_filepaths


def get_args():
    parser = argparse.ArgumentParser("Get arguments to download a video or an audio from YouTube")

    parser.add_argument('video_urls',
                        type=str,
                        nargs='+',
                        help="URL of the videos to download (space separated).")
    parser.add_argument('-a', '--audio-only',
                        action='store_true',
                        help="Whether to only download the audio (of a music video).")
    parser.add_argument('--audio-conf',
                        type=str,
                        default=DEFAULT_YT_DL_AUDIO_CONF,
                        help="Path to the configuration file for audio download.")
    parser.add_argument('--video-conf',
                        type=str,
                        default=DEFAULT_YT_DL_VIDEO_CONF,
                        help="Path to the configuration file for video download.")
    parser.add_argument('--ffmpeg-location',
                        type=str,
                        default="/usr/bin/",
                        help="Directory of the ffmpeg binary (required for audio).")
    parser.add_argument('--executable-path',
                        type=str,
                        default=YT_DL_EXEC_PATH,
                        help="Path to the youtube-dl executable.")
    parser.add_argument('--video-template',
                        type=str,
                        default=DEFAULT_TEMPLATE,
                        help="Filename template of the downloaded video(s).")
    parser.add_argument('--audio-template',
                        type=str,
                        default='%(artist)s{}%(track)s.%(ext)s'.format(SEP_CHAR),
                        help="Filename template of the downloaded audio(s).")
    parser.add_argument('--video-out-dir',
                        type=str,
                        default=DEFAULT_VIDEO_DIR,
                        help="Video output directory.")
    parser.add_argument('--audio-out-dir',
                        type=str,
                        default=DEFAULT_AUDIO_DIR,
                        help="Audio output directory.")
    parser.add_argument('--audio_playlist',
                        type=str,
                        default="iPod_musique",
                        help="Name of the playlist to create in 'audio_output_dir'.")

    args = parser.parse_args()

    # Handle both video and audio
    if args.audio_only:
        args.conf = args.audio_conf
        args.out_dir = os.path.join(args.audio_out_dir, args.audio_playlist)
        args.template = args.audio_template
    else:
        args.conf = args.video_conf
        args.out_dir = args.video_out_dir
        args.template = args.video_template

    # Sanity checks
    if not os.path.isfile(args.conf):
        raise RuntimeError("Configuration file {} does not exist.".format(os.path.abspath(args.conf)))
    if not os.path.isdir(args.out_dir):
        raise RuntimeError("Output directory {} does not exist.".format(args.out_dir))
    if (args.audio_only and not os.path.isdir(args.ffmpeg_location)):
        raise RuntimeError("FFMPEG bin directory {} does not exist.".format(args.ffmpeg_location))
    if not args.template:
        args.template = DEFAULT_TEMPLATE

    # Add template to output path
    args.output = os.path.join(args.out_dir, args.template)

    return args


def main(args):
    args = get_args()
    youtube_dl_cmd = [args.executable_path, *args.video_urls, '--output', args.output, '--ffmpeg-location', args.ffmpeg_location, '--config-location', args.conf]
    stdout_result = subprocess.Popen(youtube_dl_cmd, stdout=subprocess.PIPE, universal_newlines=True).communicate()[0]
    print(stdout_result)

    pattern = os.path.join(args.out_dir, "").replace("\\", "\\\\") + "[0-9a-zA-Z{}_\-\.]+".format(SEP_CHAR)
    filepaths = re.findall(pattern, stdout_result)
    filepaths = [filepath for filepath in set(filepaths) if os.path.isfile(filepath)]

    print("Downloaded output files in {}:".format(args.out_dir))
    if args.audio_only:
        filepaths = audiofiles_postprocessing(args.out_dir, filepaths)
    else:
        print('\n'.join(filepaths))


if __name__=='__main__':
    main()
