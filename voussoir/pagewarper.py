import cv2
import numpy as np


class Marker:
    id_table = (8, 2, 4, 15, 6, 13, 11, 1, 0, 10, 12, 7, 14, 5, 3, 9)
    rotations = {
        0: ('0°', None),
        1: ('90°', cv2.ROTATE_90_COUNTERCLOCKWISE),
        2: ('180°', cv2.ROTATE_180),
        3: ('270°', cv2.ROTATE_90_CLOCKWISE),
    }

    def __init__(self, mid, rotation, bits, points, homography):
        self.points = points
        self.homography = homography
        self.bits = bits
        self.id = mid
        self.rotation = rotation

    def rotation_text(self):
        return Marker.rotations[self.rotation][0]

    def __str__(self):
        return '#{0} {1}'.format(self.id, self.rotation_text())

    def __repr__(self):
        return 'Marker({0},{1},{2})'.format(self.id, self.rotation_text(), self.points)

    @staticmethod
    def check_rotation(marker):
        if marker[[0, 5]].any() or marker[:, [0, 5]].any():
            raise RuntimeError('Marker doesnt have a black border')
        if not (marker[[1, 4], 2:4].all() and marker[2:4, [1, 4]].all()):
            raise RuntimeError('Marker doesnt have a white inner')

        # get the orientation marker fields in a single matrix and mark the black one(s)
        orientation = np.not_equal(marker[np.ix_([1, 4], [1, 4])], 255)
        if np.count_nonzero(orientation) != 1:
            raise RuntimeError('Multiple or no orientation markers found {0}'.format(str(orientation)))

        if orientation[0][1]:
            return 1
        elif orientation[1][1]:
            return 2
        elif orientation[1][0]:
            return 3
        else:  # orientation[0][0]
            return 0

    @staticmethod
    def create(image, square, size=180):
        src_points = np.array(square.copy(), dtype=np.float32).reshape((4, 2))
        dst_points = np.array([[0, 0], [0, size], [size, size], [size, 0]], dtype=np.float32)

        term = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 20, 0.03)
        cv2.cornerSubPix(image, src_points, (3, 3), (-1, -1), term)
        homography, mask = cv2.findHomography(src_points, dst_points)

        marker_big = cv2.warpPerspective(image, homography, (size, size))
        marker_small = cv2.resize(marker_big,(6,6))
        thr, marker = cv2.threshold(marker_small,0,255,cv2.THRESH_OTSU)


        rotation = Marker.check_rotation(marker)

        if rotation != 0:
            marker = cv2.rotate(marker, Marker.rotations[rotation][1])
            src_points = np.roll(src_points, rotation, axis=0)

        id_ = np.packbits(np.logical_not(marker[2:4, 2:4]))[0] >> 4

        return Marker(Marker.id_table[id_], rotation, np.logical_not(marker[2:4, 2:4]), src_points, homography)


class LayoutInfo:
    def __init__(self, left, top, right, bottom, width, height, dpi=600.0):
        self.left = left + 0.0
        self.top = top + 0.0
        self.right = right + width
        self.bottom = bottom + height
        self.width = width
        self.height = height
        self.dpi = dpi

    def get_dst_markers(self, right=False):
        i = int(right)
        return {
            0 + 4 * i: (0, 0),
            1 + 4 * i: (self.width, 0),
            2 + 4 * i: (self.width, self.height),
            3 + 4 * i: (0, self.height)
        }

    def convert_marker(self, dst_marker):
        return (dst_marker[0] - self.left) * self.dpi, (dst_marker[1] - self.top) * self.dpi

    def get_size(self):
        return int(round((self.right - self.left) * self.dpi)), int(round((self.bottom - self.top) * self.dpi))

    def __repr__(self):
        return 'LayoutInfo({0},{1},{2},{3},{4},{5},{6})'.format(self.left, self.top, self.right, self.bottom, self.width, self.height, self.dpi)


class PageWarper:
    def __init__(self, image, max_ratio=2.2, min_area=0.0001, max_area=0.001, approx_epsilon = 0.02, debug_image = None):
        self.max_ratio = max_ratio
        self.min_area = min_area
        self.max_area = max_area
        self.approx_epsilon = approx_epsilon
        self.image = image
        self.debug_image = debug_image
        self.markers = self.__build_markers()

    def __build_markers(self):
        image = cv2.cvtColor(self.image, cv2.COLOR_BGR2GRAY)
        thresh = cv2.adaptiveThreshold(image, 128, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 11 + 20, 8)
        squares = self.__get_squares(thresh)
        markers = dict()
        for square in squares:
            try:
                marker = Marker.create(image,square)
                markers[marker.id] = marker
            except RuntimeError as e:
                #display(e)
                # ignore squares that are no markers
                pass
        return markers


    def get_warped_image(self, layout, right=False):
        dst_markers = layout.get_dst_markers(right)
        (dst_points, src_points) = self.__get_points(layout, dst_markers)

        homography, mask = cv2.findHomography(dst_points, src_points)
        return cv2.warpPerspective(self.image, homography, layout.get_size())

    def guess_layouts(self, l=0, t=0.5, r=0.5, b=0.5, dpi = 600.0):
        leftSize = self.guess_size(False)
        rightSize = self.guess_size(True)
        commonHeight = (leftSize[0][1] + rightSize[0][1]) * 0.5
        return LayoutInfo(l,t,r,b,leftSize[0][0],commonHeight,dpi), LayoutInfo(l,t,r,b,rightSize[0][0],commonHeight,dpi)
        #display(leftSize)
        #display(rightSize)

    def guess_size(self,right = False):
        # marker is 0.5 inch wide and high
        marker_size = 0.5
        dst_markers = LayoutInfo(0,0,0,0,1,1).get_dst_markers(right)
        src_points = np.zeros((len(dst_markers),2),dtype=np.float64)
        dst_points = np.zeros((len(dst_markers),2),dtype=np.float64)
        cnt = 0
        for i in dst_markers:
            if not i in self.markers:
                raise RuntimeError('Index {0} does not exist in source markers'.format(i))
            src_points[cnt] = dst_markers[i]
            dst_points[cnt] = self.markers[i].points[0]
            cnt += 1

        src_points = (src_points > 0)*1.0
        homography, mask = cv2.findHomography(dst_points,src_points)

        heights = []
        widths = []

        for i in dst_markers:
            m = self.markers[i]
            tp = self.warp(homography,m.points)
            widths.append(np.linalg.norm(tp[3]-tp[0]))
            widths.append(np.linalg.norm(tp[2]-tp[1]))
            heights.append(np.linalg.norm(tp[2]-tp[3]))
            heights.append(np.linalg.norm(tp[1]-tp[0]))

        return (marker_size/np.mean(widths),marker_size/np.mean(heights)), (np.std(widths),np.std(heights))

    def warp(self, m, s):
        s = np.array(s)
        ex = np.ones((s.shape[0], 3), dtype=s.dtype)
        ex[:, 0:2] = s
        r = m.dot(ex.T)
        return (r / r[2])[0:2].T

    def __get_points(self, layout, dst_markers):
        src_points = np.zeros((len(dst_markers), 2), dtype=np.float32)
        dst_points = np.zeros((len(dst_markers), 2), dtype=np.float32)
        cnt = 0
        for i, dst_marker in dst_markers.items():
            if not i in self.markers:
                raise RuntimeError('Index {0} does not exist in source markers'.format(i))
            src_points[cnt] = layout.convert_marker(dst_marker)
            dst_points[cnt] = self.markers[i].points[0]
            cnt += 1
        return (dst_points, src_points)

    def __get_squares(self, image):
        candidates = []
        full_area = image.shape[0] * image.shape[1]
        contours, hierarchy = cv2.findContours(image, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            if len(contour) >= 4:
                area = cv2.contourArea(contour) / full_area
                if self.min_area < area < self.max_area:
                    x, y, w, h = cv2.boundingRect(contour)
                    aspect_ratio = float(w) / h
                    if 1.0 / float(self.max_ratio) < aspect_ratio < self.max_ratio:
                        perimeter = cv2.arcLength(contour, True)
                        approx = cv2.approxPolyDP(contour, perimeter * self.approx_epsilon, True)
                        if len(approx) == 4 and cv2.isContourConvex(approx):
                            candidates.append(approx)

        return candidates
