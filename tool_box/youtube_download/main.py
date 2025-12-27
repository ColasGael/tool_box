#!/usr/bin/env python

import argparse
import os
import subprocess

try:
    from tinytag import TinyTag
    AUDIO_METADATA_AVAILABLE = True
except ImportError:
    AUDIO_METADATA_AVAILABLE = False

YT_DL_EXEC_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "youtube-dl")

# Assume they are saved in the same directory as this file
DEFAULT_YT_DL_AUDIO_CONF = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'youtube-dl_audio.conf')
DEFAULT_YT_DL_VIDEO_CONF = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'youtube-dl_video.conf')

DEFAULT_TEMPLATE = '%(title)s.%(ext)s'
# AUDIO_TEMPLARE = '%(artist)s#%(title)s.%(ext)s'
# DEFAULT_AUDIO_DIR = "D:\\Documents\\Media\\music\\playlists"
DEFAULT_AUDIO_DIR = "/home/colasg/Downloads"
# DEFAULT_VIDEO_DIR = "D:\\_temp"
DEFAULT_VIDEO_DIR = "/home/colasg/Downloads"


def get_metadata(filepath):
    metadata = TinyTag.get(filepath)
    useful_metadata = {
		'artist': metadata.artist,
		'album': metadata.album,
		'title': metadata.title,
		'genre': metadata.genre,
    }
    return useful_metadata


def audiofiles_postprocessing(temp_out_dir):
    out_dir = os.path.dirname(temp_out_dir)

    new_filepaths = []
    for filename in os.listdir(temp_out_dir):
        filepath = os.path.join(temp_out_dir, filename)
        if not os.path.isfile(filepath):
            continue

        metadata = get_metadata(filepath)
        print("Metadata for file {}: {}".format(filepath, metadata))

        artist = metadata['artist']
        title = metadata['title']
        file_ext = os.path.splitext(filename)[1]

        artist_dir = os.path.join(out_dir, artist)
        os.makedirs(artist_dir, exist_ok=True)

        new_filename = f"{artist.lower().replace(' ', '-')}_{title.lower().replace(' ', '-')}{file_ext}"
        new_filepath = os.path.join(artist_dir, new_filename)

        if os.path.isfile(new_filepath):
            print(f"Audio file {new_filepath} already exists, remove duplicate.")
            os.remove(filepath)
            continue

        os.rename(filepath, new_filepath)
        new_filepaths.append(new_filepath)

    print(f"Remove temporary directory {temp_out_dir}.")
    os.rmdir(temp_out_dir)

    print(f"Post-processed audio files: {new_filepaths}")

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
    parser.add_argument('--video-template',
                        type=str,
                        default=DEFAULT_TEMPLATE,
                        help="Filename template of the downloaded video(s).")
    parser.add_argument('--audio-template',
                        type=str,
                        default=DEFAULT_TEMPLATE,
                        help="Filename template of the downloaded audio(s).")
    parser.add_argument('--video-out-dir',
                        type=str,
                        default=DEFAULT_VIDEO_DIR,
                        help="Video output directory.")
    parser.add_argument('--audio-out-dir',
                        type=str,
                        default=DEFAULT_AUDIO_DIR,
                        help="Audio output directory.")

    args = parser.parse_args()

    # Handle both video and audio
    if args.audio_only:
        args.conf = args.audio_conf
        # Use a unique sub-directory to identify the file that needs to be post-processed
        args.out_dir = os.path.join(args.audio_out_dir, "audio", f"tmp_audio_{os.getpid()}")
        if os.path.exists(args.out_dir):
            raise RuntimeError(f"Temporary audio output directory {args.out_dir} already exists.")
        os.makedirs(args.out_dir)
        args.template = args.audio_template
    else:
        args.conf = args.video_conf
        args.out_dir = os.path.join(args.audio_out_dir, "video")
        os.makedirs(args.out_dir, exist_ok=True)
        args.template = args.video_template

    args.conf = os.path.abspath(args.conf)
    args.out_dir = os.path.abspath(args.out_dir)

    # Sanity checks
    if not os.path.isfile(args.conf):
        raise RuntimeError(f"Configuration file {args.conf} does not exist.")
    if not os.path.isdir(args.out_dir):
        raise RuntimeError(f"Output directory {args.out_dir} does not exist.")
    if (args.audio_only and not os.path.isdir(args.ffmpeg_location)):
        raise RuntimeError(f"FFMPEG bin directory {args.ffmpeg_location} does not exist.")
    if not args.template:
        args.template = DEFAULT_TEMPLATE

    # Add template to output path
    args.output = os.path.join(args.out_dir, args.template)

    return args


def main():
    args = get_args()
    youtube_dl_cmd = [YT_DL_EXEC_PATH, *args.video_urls, '--output', args.output, '--ffmpeg-location', args.ffmpeg_location, '--config-location', args.conf]
    subprocess.run(youtube_dl_cmd)

    # Post-process the audio files
    if args.audio_only and AUDIO_METADATA_AVAILABLE:
        audiofiles_postprocessing(args.out_dir)


if __name__=='__main__':
    main()
