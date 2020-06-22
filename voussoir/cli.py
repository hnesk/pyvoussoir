#! /usr/bin/python3
"""pyvoussoir

Description:
    This program takes images of books (each picture including a two-page spread), detects special glyphs pasted in the corners of the book, and de-keystones and thereby digitally flattens the pages. It then automatically separates the pages into separate, cropped image files

Usage:
      pyvoussoir
      pyvoussoir (-h | --help)
      pyvoussoir (-v | --version)
      pyvoussoir [--verbose] [--no-left-page] [--no-right-page] [-w <page_width_argument>] [-t <page_height_argument>] [-i <input_image>] [<output_image_one>] [<output_image_two>]
      pyvoussoir [--verbose] [--no-left-page] [--no-right-page] [-w <page_width_argument>] [-t <page_height_argument>] [-d <dpi>] [--offset-left-page-left-side <offset_left_page_left_side>] [--offset-left-page-right-side <offset_left_page_right_side>] [--offset-left-page-top-side <offset_left_page_top_side>] [--offset-left-page-bottom-side <offset_left_page_bottom_side>] [--offset-right-page-left-side <offset_right_page_left_side>] [--offset-right-page-right-side <offset_right_page_right_side>] [--offset-right-page-top-side <offset_right_page_top_side>] [--offset-right-page-bottom-side <offset_right_page_bottom_side>] [-i <input_image>] [<output_image_one>] [<output_image_two>]

Options:
      -h --help     Show this screen.
      -v --version  Show version.

      --verbose     Show additional output, including the values of every option the program accepts.

      -t --page-height=<page_height_argument>  Height of each page (in any metric) ('t' is for 'tall'). [default: 9.5]
      -w --page-width=<page_width_argument>  Width of each page (in any metric). [default: 6.0]
      --no-left-page  Only process right-side pages (Markers 0-3).
      --no-right-page  Only process left-side pages (Markers 4-7).

      -d --dpi=<dpi>  The DPI level at which to save the output images. [default: 600.0]

      -i --input-image=<input_image>  The input image.

      <output_image_one>  The output image. Needs to have an image-like file extension (e.g., ".jpg", ".JPG", ".png", ".tif", ".tiff").
      <output_image_two>  If relevant, the second output image (see <output_image_one> above).

      --offset-left-page-left-side=<offset_left_page_left_side>  Page offset, in the same units as page height and width. [default: 0.00]
      --offset-left-page-right-side=<offset_left_page_right_side>  Page offset, in the same units as page height and width. [default: 0.00]
      --offset-left-page-top-side=<offset_left_page_top_side>  Page offset, in the same units as page height and width. [default: 0.00]
      --offset-left-page-bottom-side=<offset_left_page_bottom_side>  Page offset, in the same units as page height and width. [default: 0.00]

      --offset-right-page-left-side=<offset_right_page_left_side>  Page offset, in the same units as page height and width. [default: 0.00]
      --offset-right-page-right-side=<offset_right_page_right_side>  Page offset, in the same units as page height and width. [default: 0.00]
      --offset-right-page-top-side=<offset_right_page_top_side>  Page offset, in the same units as page height and width. [default: 0.00]
      --offset-right-page-bottom-side=<offset_right_page_bottom_side>  Page offset, in the same units as page height and width. [default: 0.00]

Placing markers:
    Within the docs directory, you'll find PDF and Adobe Illustrator / Inkscape versions of a series of 15 "glyphs," small images that each comprises a unique pattern of pixels in a 6x6 grid. You'll need to print and cut out the glyphs; at the moment, only glyphs 0-3 (left page) and 4-7 (right page) are needed. Tape or otherwise affix the glyphs in clockwise order around the perimeter of each book page (for example, if you're using a glass or acrylic platen to flatten the pages of a book, affix the glyphs in each corner of the platen: starting at the top left and moving clockwise to the center/spine of the book, place glyphs 0, 1, 2, and 3 around the left page, and (again from top left and moving clockwise) glyphs 4, 5, 6, and 7 on the right page. The program will, by default, crop to the inside vertical, outside horizontal edge of the glyphs it detects. This can be adjusted using the offset arguments defined above. The offset arguments can be positive or negative (e.g., setting --offset-left-page-left-side to -0.5 will move the crop line to the left 0.5 units).
"""

from docopt import docopt
from schema import Schema, And, Use, Or, SchemaError
import os
import cv2
from voussoir.pagewarper import PageWarper, LayoutInfo


def validate(args):
    def ensure_opencv_filename(filename):
        ext = os.path.splitext(filename)[1].lstrip('.').lower()
        opencv_exts = ['bmp', 'dib', 'jpg', 'jpeg', 'jpe', 'jp2', 'png', 'webp', 'pbm', 'pgm', 'ppm', 'sr', 'ras',
                       'tiff', 'tif']

        if not ext in opencv_exts:
            raise RuntimeError(
                'Wrong image file extension "{0}". Please use an OpenCV supported image file extension: {1}'.format(ext,
                                                                                                                    ','.join(
                                                                                                                        opencv_exts)))

    def non_existing_image(filename):
        if os.path.exists(filename):
            raise SchemaError('File "{0}" already exists'.format(filename))
        ensure_opencv_filename(filename)
        return os.path.realpath(filename)

    def existing_image(filename):
        if not filename:
            raise SchemaError('No file given')
        if not os.path.exists(filename):
            raise SchemaError('File "{0}" does not exist'.format(filename))
        ensure_opencv_filename(filename)
        return os.path.realpath(filename)

    schema = Schema({
        '--dpi': And(Use(float), lambda dpi: 0 < dpi <= 1200, error='Please enter a dpi value between 1 and 1200'),
        '--help': Use(bool),
        '--input-image': Use(existing_image),
        '--no-left-page': Use(bool),
        '--no-right-page': Use(bool),
        '--offset-left-page-bottom-side': Use(float, error='Please enter the offset as a float'),
        '--offset-left-page-left-side': Use(float, error='Please enter the offset as a float'),
        '--offset-left-page-right-side': Use(float, error='Please enter the offset as a float'),
        '--offset-left-page-top-side': Use(float, error='Please enter the offset as a float'),
        '--offset-right-page-bottom-side': Use(float, error='Please enter the offset as a float'),
        '--offset-right-page-left-side': Use(float, error='Please enter the offset as a float'),
        '--offset-right-page-right-side': Use(float, error='Please enter the offset as a float'),
        '--offset-right-page-top-side': Use(float, error='Please enter the offset as a float'),
        '--page-height': Use(float, error='Please enter the height as a float'),
        '--page-width': Use(float, error='Please enter the width as a float'),
        '--verbose': Use(bool),
        '--version': Use(bool),
        '<output_image_one>': Or(None, Use(non_existing_image)),
        '<output_image_two>': Or(None, Use(non_existing_image))
    })

    args = schema.validate(args)
    if not (args['--no-left-page'] or args['<output_image_one>']):
        raise RuntimeError('You either have to specify --no-left-page or <output_image_one>')
    if not (args['--no-right-page'] or args['<output_image_two>']):
        raise RuntimeError('You either have to specify --no-right-page or <output_image_two>')

    return args


def process(args):
    image = cv2.imread(args['--input-image'])
    page_width = args['--page-width']
    page_height = args['--page-height']
    dpi = args['--dpi']

    pw = PageWarper(image)

    for i, side in enumerate(['left', 'right']):
        if not args['--no-' + side + '-page']:
            layout = LayoutInfo(
                0.0 + args['--offset-' + side + '-page-left-side'],
                0.0 + args['--offset-' + side + '-page-top-side'],
                0.0 + args['--offset-' + side + '-page-right-side'],
                0.0 + args['--offset-' + side + '-page-bottom-side'],
                page_width,
                page_height,
                dpi
            )
            print(layout)
            page_image = pw.get_warped_image(layout, bool(i))
            filename = '<output_image_' + ('one' if i == 0 else 'two') + '>'
            cv2.imwrite(args[filename], page_image)


def main():
    args = docopt(__doc__, version='pyvouissour 0.2')
    args = validate(args)
    process(args)
