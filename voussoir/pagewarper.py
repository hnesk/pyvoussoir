from typing import Dict, Tuple, List, cast

import cv2
import numpy as np

Vector = Tuple[float, float]
VectorMap = Dict[int, Vector]


class Marker:
    id_lookup = (8, 2, 4, 15, 6, 13, 11, 1, 0, 10, 12, 7, 14, 5, 3, 9)
    rotations = {
        0: ('0°', None),
        1: ('90°', cv2.ROTATE_90_COUNTERCLOCKWISE),
        2: ('180°', cv2.ROTATE_180),
        3: ('270°', cv2.ROTATE_90_CLOCKWISE),
    }

    def __init__(self, mid: int, rotation: int, bits: np.array, points: np.array, homography: np.array):
        self.points: np.array = points
        self.homography: np.array = homography
        self.bits: np.array = bits
        self.id: int = mid
        self.rotation: int = rotation

    def rotation_text(self) -> str:
        return Marker.rotations[self.rotation][0]

    def __str__(self) -> str:
        return '#{0} {1}'.format(self.id, self.rotation_text())

    def __repr__(self) -> str:
        return 'Marker({0},{1},{2})'.format(self.id, self.rotation_text(), self.points)

    @staticmethod
    def check_rotation(marker: np.array) -> int:
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
    def create(image: np.array, square: np.array, size: int = 180) -> 'Marker':
        src_points = np.array(square.copy(), dtype=np.float32).reshape((4, 2))
        dst_points = np.array([[0, 0], [0, size], [size, size], [size, 0]], dtype=np.float32)

        term = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 20, 0.03)
        cv2.cornerSubPix(image, src_points, (3, 3), (-1, -1), term)
        homography, mask = cv2.findHomography(src_points, dst_points)

        marker_big = cv2.warpPerspective(image, homography, (size, size))
        marker_small = cv2.resize(marker_big, (6, 6))
        thr, marker = cv2.threshold(marker_small, 0, 255, cv2.THRESH_OTSU)

        rotation = Marker.check_rotation(marker)

        if rotation != 0:
            marker = cv2.rotate(marker, Marker.rotations[rotation][1])
            src_points = np.roll(src_points, rotation, axis=0)

        id_ = np.packbits(np.logical_not(marker[2:4, 2:4]))[0] >> 4

        return Marker(Marker.id_lookup[id_], rotation, np.logical_not(marker[2:4, 2:4]), src_points, homography)


class LayoutInfo:
    def __init__(self, left: float, top: float, right: float, bottom: float, width: float, height: float,
                 dpi: float = 600.0):
        self.left = left + 0.0
        self.top = top + 0.0
        self.right = right + width
        self.bottom = bottom + height
        self.width = width
        self.height = height
        self.dpi = dpi

    def get_dst_markers(self, right: bool = False) -> VectorMap:
        i = int(right)
        return {
            0 + 4 * i: (0, 0),
            1 + 4 * i: (self.width, 0),
            2 + 4 * i: (self.width, self.height),
            3 + 4 * i: (0, self.height)
        }

    def convert_marker(self, dst_marker: Vector) -> Vector:
        return (dst_marker[0] - self.left) * self.dpi, (dst_marker[1] - self.top) * self.dpi

    def get_size(self) -> Tuple[int, int]:
        return int(round((self.right - self.left) * self.dpi)), int(round((self.bottom - self.top) * self.dpi))

    def __repr__(self) -> str:
        return 'LayoutInfo({0},{1},{2},{3},{4},{5},{6})'.format(self.left, self.top, self.right, self.bottom,
                                                                self.width, self.height, self.dpi)


class PageWarper:
    def __init__(self, max_ratio: float = 2.2, min_area: float = 0.0001, max_area: float = 0.001,
                 approx_epsilon: float = 0.02):
        self.max_ratio: float = max_ratio
        self.min_area: float = min_area
        self.max_area: float = max_area
        self.approx_epsilon: float = approx_epsilon
        self.image: np.array = None
        self.markers: Dict[int, Marker] = {}

    def set_image(self, image: np.array) -> None:
        self.image = image
        self.markers = self.__build_markers()

    def __build_markers(self) -> Dict[int, Marker]:
        image = cv2.cvtColor(self.image, cv2.COLOR_BGR2GRAY)
        thresh = cv2.adaptiveThreshold(image, 128, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 11 + 20, 8)
        squares = self._get_squares(thresh)
        markers = dict()
        for square in squares:
            try:
                marker = Marker.create(image, square)
                markers[marker.id] = marker
            except RuntimeError:
                # ignore squares that are no markers
                pass
        return markers

    def get_warped_image(self, layout: LayoutInfo, right: bool = False) -> np.array:
        dst_markers = layout.get_dst_markers(right)
        (dst_points, src_points) = self._get_points(layout, dst_markers)

        homography, mask = cv2.findHomography(dst_points, src_points)
        return cv2.warpPerspective(self.image, homography, layout.get_size())

    def guess_layouts(self, left: float = 0, top: float = 0.5, right: float = 0.5, bottom: float = 0.5,
                      dpi: float = 600.0) -> Tuple[LayoutInfo, LayoutInfo]:
        left_size = self.guess_size(False)
        right_size = self.guess_size(True)
        common_height = (left_size[0][1] + right_size[0][1]) * 0.5
        return (
            LayoutInfo(left, top, right, bottom, left_size[0][0], common_height, dpi),
            LayoutInfo(left, top, right, bottom, right_size[0][0], common_height, dpi)
        )

    def guess_size(self, right: bool = False) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        # marker is 0.5 inch wide and high
        marker_size: float = 0.5
        dst_markers = LayoutInfo(0, 0, 0, 0, 1, 1).get_dst_markers(right)
        src_points = np.zeros((len(dst_markers), 2), dtype=np.float64)
        dst_points = np.zeros((len(dst_markers), 2), dtype=np.float64)
        cnt = 0
        for i in dst_markers:
            if i not in self.markers:
                raise RuntimeError('Index {0} does not exist in source markers'.format(i))
            src_points[cnt] = dst_markers[i]
            dst_points[cnt] = self.markers[i].points[0]
            cnt += 1

        src_points = (src_points > 0) * 1.0
        homography, mask = cv2.findHomography(dst_points, src_points)

        heights: List[float] = []
        widths: List[float] = []

        for i in dst_markers:
            m = self.markers[i]
            tp = self._warp(homography, m.points)
            widths.append(np.linalg.norm(tp[3] - tp[0]))
            widths.append(np.linalg.norm(tp[2] - tp[1]))
            heights.append(np.linalg.norm(tp[2] - tp[3]))
            heights.append(np.linalg.norm(tp[1] - tp[0]))

        return (marker_size / cast(float, np.mean(widths)), marker_size / cast(float, np.mean(heights))), (
        cast(float, np.std(widths)), cast(float, np.std(heights)))

    @staticmethod
    def _warp(m: np.array, s: np.array) -> np.array:
        s = np.array(s)
        ex = np.ones((s.shape[0], 3), dtype=s.dtype)
        ex[:, 0:2] = s
        r = m.dot(ex.T)
        return (r / r[2])[0:2].T

    def _get_points(self, layout: LayoutInfo, dst_markers: VectorMap) -> Tuple[np.array, np.array]:
        src_points = np.zeros((len(dst_markers), 2), dtype=np.float32)
        dst_points = np.zeros((len(dst_markers), 2), dtype=np.float32)
        cnt = 0
        for i, dst_marker in dst_markers.items():
            if i not in self.markers:
                raise RuntimeError('Index {0} does not exist in source markers'.format(i))
            src_points[cnt] = layout.convert_marker(dst_marker)
            dst_points[cnt] = self.markers[i].points[0]
            cnt += 1
        return dst_points, src_points

    def _get_squares(self, image: np.array) -> np.array:
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
