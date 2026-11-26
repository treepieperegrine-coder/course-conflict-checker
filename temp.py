import json
import random
import socket
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Callable, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse


# ==============================================================================
# [組員 2 - Tech Lead] 統一資料結構介面：Course 課程／活動物件
# ==============================================================================
PERIOD_TIMES = {
    1: ("08:10", "09:00"),
    2: ("09:10", "10:00"),
    3: ("10:10", "11:00"),
    4: ("11:10", "12:00"),
    5: ("13:30", "14:20"),
    6: ("14:30", "15:20"),
    7: ("15:30", "16:20"),
    8: ("16:30", "17:20"),
    9: ("17:30", "18:20"),
    10: ("18:30", "19:20"),
    11: ("19:25", "20:15"),
    12: ("20:20", "21:10"),
}

DAY_NAMES = ["", "週一", "週二", "週三", "週四", "週五", "週六", "週日"]


def time_str_to_minutes(t_str: str) -> int:
    hh, mm = map(int, t_str.split(":"))
    return hh * 60 + mm


def _manual_sort_ints(arr: List[int]) -> List[int]:
    """手動插入排序，避免呼叫內建 sorted()。"""
    res = [x for x in arr]
    for i in range(1, len(res)):
        key = res[i]
        j = i - 1
        while j >= 0 and res[j] > key:
            res[j + 1] = res[j]
            j -= 1
        res[j + 1] = key
    return res


class Course:
    """全組統一之課程／活動資料模型（相容 Python 3.6+）。"""

    def __init__(
        self,
        code: str,
        name: str,
        dept: str,
        category: str,
        priority: int,
        credits: int,
        teacher: str,
        room: str,
        day: int,
        periods: List[int],
        capacity: int = 50,
        enrolled_count: int = 10,
    ):
        self.code = code                        # 課程代碼 / 活動 ID
        self.name = name                        # 課程 / 活動名稱
        self.dept = dept                        # 開課單位
        self.category = category                # 必修 / 選修 / 通識 / 社團
        self.priority = priority                # 優先度（1=必修最高, 2=選修, 3=通識, 4=社團）
        self.credits = credits                  # 學分數
        self.teacher = teacher                  # 授課教師 / 負責人
        self.room = room                        # 上課教室 / 地點
        self.day = day                          # 星期 1~7
        self.periods = _manual_sort_ints(periods)
        self.start_period = self.periods[0]
        self.end_period = self.periods[-1]
        self.start_str = PERIOD_TIMES[self.start_period][0]
        self.end_str = PERIOD_TIMES[self.end_period][1]
        self.start_min = time_str_to_minutes(self.start_str)
        self.end_min = time_str_to_minutes(self.end_str)
        self.capacity = capacity                # 人數上限（供候補機制測試）
        self.enrolled_count = enrolled_count    # 目前修課人數

    def overlaps_with(self, other: "Course") -> bool:
        """判斷兩門課程是否時間衝堂（同日且時間區間嚴格重疊）。"""
        if self.day != other.day:
            return False
        return self.start_min < other.end_min and other.start_min < self.end_min

    def time_label(self) -> str:
        p_str = ",".join(str(p) for p in self.periods)
        return f"{DAY_NAMES[self.day]} 第{p_str}節 ({self.start_str}-{self.end_str})"

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "name": self.name,
            "dept": self.dept,
            "category": self.category,
            "priority": self.priority,
            "credits": self.credits,
            "teacher": self.teacher,
            "room": self.room,
            "day": self.day,
            "dayName": DAY_NAMES[self.day],
            "periods": self.periods,
            "startMin": self.start_min,
            "endMin": self.end_min,
            "timeLabel": self.time_label(),
            "capacity": self.capacity,
            "enrolledCount": self.enrolled_count,
        }


# ==============================================================================
# [組員 1] 課程／活動資料庫模組：Hash Table（鏈結法 Separate Chaining）
# 複雜度：新增/刪除/查詢 平均 O(1)、最差 O(N)；Rehash 擴容 O(N)
# ==============================================================================
class HashNode:
    """雜湊桶鏈結節點。"""

    def __init__(self, key: str, value: object, next_node: Optional["HashNode"] = None):
        self.key = key
        self.value = value
        self.next = next_node


class CustomHashTable:
    """純手動實作之雜湊表（使用固定大小陣列 + HashNode 單向鏈結串列處理碰撞）。"""

    def __init__(self, capacity: int = 16):
        self.capacity = capacity
        self.size = 0
        self.buckets: List[Optional[HashNode]] = [None] * capacity

    def _hash(self, key: str) -> int:
        """多項式滾動雜湊函數（Polynomial Rolling Hash）。"""
        h = 0
        for ch in key:
            h = (h * 31 + ord(ch)) % self.capacity
        return h

    def _rehash(self) -> None:
        """負載因子 > 0.75 時擴容為兩倍並重新雜湊：O(N)。"""
        old_buckets = self.buckets
        self.capacity *= 2
        self.buckets = [None] * self.capacity
        self.size = 0
        for head in old_buckets:
            curr = head
            while curr is not None:
                self.insert(curr.key, curr.value)
                curr = curr.next

    def insert(self, key: str, value: object) -> None:
        """新增或更新資料：平均 O(1)，最差 O(N)。"""
        if self.size / self.capacity > 0.75:
            self._rehash()

        idx = self._hash(key)
        curr = self.buckets[idx]
        while curr is not None:
            if curr.key == key:
                curr.value = value
                return
            curr = curr.next

        new_node = HashNode(key, value, self.buckets[idx])
        self.buckets[idx] = new_node
        self.size += 1

    def search(self, key: str) -> Optional[object]:
        """依鍵值查詢資料：平均 O(1)，最差 O(N)。"""
        idx = self._hash(key)
        curr = self.buckets[idx]
        while curr is not None:
            if curr.key == key:
                return curr.value
            curr = curr.next
        return None

    def search_with_debug(self, key: str) -> Tuple[Optional[object], int, int]:
        """回傳 (物件, 桶位索引, 碰撞鏈探測步數)，供系統展示 Hash Table 運作。"""
        idx = self._hash(key)
        curr = self.buckets[idx]
        steps = 0
        while curr is not None:
            steps += 1
            if curr.key == key:
                return curr.value, idx, steps
            curr = curr.next
        return None, idx, steps

    def delete(self, key: str) -> bool:
        """依鍵值刪除資料：平均 O(1)，最差 O(N)。"""
        idx = self._hash(key)
        curr = self.buckets[idx]
        prev: Optional[HashNode] = None
        while curr is not None:
            if curr.key == key:
                if prev is None:
                    self.buckets[idx] = curr.next
                else:
                    prev.next = curr.next
                self.size -= 1
                return True
            prev = curr
            curr = curr.next
        return False

    def values(self) -> List[object]:
        """遍歷所有儲存項目：O(N + Capacity)。"""
        result: List[object] = []
        for head in self.buckets:
            curr = head
            while curr is not None:
                result.append(curr.value)
                curr = curr.next
        return result


# ==============================================================================
# [組員 3] 課表排序與輸出模組：Merge Sort（合併排序，嚴禁呼叫內建 sort()）
# 複雜度：時間 O(N log N)，空間 O(N)
# ==============================================================================
def merge_sort_courses(courses: List[Course], mode: str = "time") -> List[Course]:
    """
    手寫穩定合併排序 O(N log N)：
    - mode == 'time':     依「星期 -> 開始時間 -> 結束時間」排序
    - mode == 'credits':  依「學分數（由高到低） -> 星期 -> 開始時間」排序
    - mode == 'priority': 依「優先度（必修1 -> 社團4） -> 星期 -> 開始時間」排序
    - mode == 'end':      依「星期 -> 結束時間 -> 開始時間」排序（供貪婪排課）
    """
    n = len(courses)
    if n <= 1:
        return [c for c in courses]

    mid = n // 2
    left = merge_sort_courses(courses[:mid], mode)
    right = merge_sort_courses(courses[mid:], mode)
    return _merge_two_sorted(left, right, mode)


def _compare_course(a: Course, b: Course, mode: str) -> bool:
    """回傳 True 代表 a 應排在 b 前面（維持穩定性 <=）。"""
    if mode == "credits":
        key_a = (-a.credits, a.day, a.start_min, a.code)
        key_b = (-b.credits, b.day, b.start_min, b.code)
    elif mode == "priority":
        key_a = (a.priority, a.day, a.start_min, a.code)
        key_b = (b.priority, b.day, b.start_min, b.code)
    elif mode == "end":
        key_a = (a.day, a.end_min, a.start_min, a.code)
        key_b = (b.day, b.end_min, b.start_min, b.code)
    else:
        key_a = (a.day, a.start_min, a.end_min, a.code)
        key_b = (b.day, b.start_min, b.end_min, b.code)
    return key_a <= key_b


def _merge_two_sorted(left: List[Course], right: List[Course], mode: str) -> List[Course]:
    merged: List[Course] = []
    i = 0
    j = 0
    len_l = len(left)
    len_r = len(right)
    while i < len_l and j < len_r:
        if _compare_course(left[i], right[j], mode):
            merged.append(left[i])
            i += 1
        else:
            merged.append(right[j])
            j += 1
    while i < len_l:
        merged.append(left[i])
        i += 1
    while j < len_r:
        merged.append(right[j])
        j += 1
    return merged


# ==============================================================================
# [組員 4] 個人已選清單模組：Linked List（單向鏈結串列）
# 複雜度：頭部新增 O(1)、尾部新增 O(N)、刪除 O(N)、查詢 O(N)、遍歷 O(N)
# ==============================================================================
class CourseListNode:
    """個人已選課程鏈結節點。"""

    def __init__(self, course: Course, next_node: Optional["CourseListNode"] = None):
        self.course = course
        self.next = next_node


class EnrolledLinkedList:
    """單向鏈結串列管理使用者已選課表。"""

    def __init__(self):
        self.head: Optional[CourseListNode] = None
        self.count = 0

    def insert_head(self, course: Course) -> bool:
        """頭部插入節點：O(1)。"""
        if self.search(course.code) is not None:
            return False
        self.head = CourseListNode(course, self.head)
        self.count += 1
        return True

    def insert_tail(self, course: Course) -> bool:
        """尾部插入節點（保持加選先後順序）：O(N)。"""
        if self.search(course.code) is not None:
            return False
        new_node = CourseListNode(course)
        if self.head is None:
            self.head = new_node
        else:
            curr = self.head
            while curr.next is not None:
                curr = curr.next
            curr.next = new_node
        self.count += 1
        return True

    def delete(self, code: str) -> Optional[Course]:
        """依課程代碼刪除節點並回傳被退選的課程：O(N)。"""
        curr = self.head
        prev: Optional[CourseListNode] = None
        while curr is not None:
            if curr.course.code == code:
                if prev is None:
                    self.head = curr.next
                else:
                    prev.next = curr.next
                self.count -= 1
                return curr.course
            prev = curr
            curr = curr.next
        return None

    def search(self, code: str) -> Optional[Course]:
        """查詢課程是否已在已選清單中：O(N)。"""
        curr = self.head
        while curr is not None:
            if curr.course.code == code:
                return curr.course
            curr = curr.next
        return None

    def traverse(self) -> List[Course]:
        """從 HEAD 遍歷輸出所有已選課程：O(N)。"""
        result: List[Course] = []
        curr = self.head
        while curr is not None:
            result.append(curr.course)
            curr = curr.next
        return result


# ==============================================================================
# [組員 5] 操作復原／候補機制：Stack（復原堆疊） & Queue（候補排隊佇列）
# 複雜度：Push/Enqueue O(1)、Pop/Dequeue O(1)、Peek/Front O(1)、isEmpty O(1)
# ==============================================================================
class StackNode:
    def __init__(self, action: str, course_code: str, next_node: Optional["StackNode"] = None):
        self.action = action            # 'ADD' 或 'DROP'
        self.course_code = course_code
        self.next = next_node


class UndoStack:
    """LIFO 堆疊：記錄加退選歷史，支援「上一步 (Undo)」復原。"""

    def __init__(self):
        self.top: Optional[StackNode] = None
        self.size = 0

    def push(self, action: str, course_code: str) -> None:
        self.top = StackNode(action, course_code, self.top)
        self.size += 1

    def pop(self) -> Optional[Tuple[str, str]]:
        if self.top is None:
            return None
        node = self.top
        self.top = self.top.next
        self.size -= 1
        return (node.action, node.course_code)

    def peek(self) -> Optional[Tuple[str, str]]:
        if self.top is None:
            return None
        return (self.top.action, self.top.course_code)

    def is_empty(self) -> bool:
        return self.top is None

    def to_list(self) -> List[dict]:
        items: List[dict] = []
        curr = self.top
        while curr is not None:
            items.append({"action": curr.action, "code": curr.course_code})
            curr = curr.next
        return items


class QueueNode:
    def __init__(self, student_name: str, course_code: str, next_node: Optional["QueueNode"] = None):
        self.student_name = student_name
        self.course_code = course_code
        self.next = next_node


class WaitlistQueue:
    """FIFO 佇列：熱門額滿課程退選後，依排隊順序自動遞補。"""

    def __init__(self):
        self.front_node: Optional[QueueNode] = None
        self.rear_node: Optional[QueueNode] = None
        self.size = 0

    def enqueue(self, student_name: str, course_code: str) -> None:
        new_node = QueueNode(student_name, course_code)
        if self.rear_node is None:
            self.front_node = new_node
            self.rear_node = new_node
        else:
            self.rear_node.next = new_node
            self.rear_node = new_node
        self.size += 1

    def dequeue(self) -> Optional[Tuple[str, str]]:
        if self.front_node is None:
            return None
        node = self.front_node
        self.front_node = self.front_node.next
        if self.front_node is None:
            self.rear_node = None
        self.size -= 1
        return (node.student_name, node.course_code)

    def front(self) -> Optional[Tuple[str, str]]:
        if self.front_node is None:
            return None
        return (self.front_node.student_name, self.front_node.course_code)

    def is_empty(self) -> bool:
        return self.front_node is None

    def to_list(self) -> List[dict]:
        items: List[dict] = []
        curr = self.front_node
        while curr is not None:
            items.append({"student": curr.student_name, "code": curr.course_code})
            curr = curr.next
        return items


# ==============================================================================
# [組員 6] 空堂時段搜尋模組：BST（二元搜尋樹）
# 複雜度：新增/刪除/查詢 平均 O(log N)、最差 O(N)；中序遍歷 O(N)
# ==============================================================================
class BSTNode:
    def __init__(self, course: Course):
        self.course = course
        self.key = (course.day, course.start_min, course.code)
        self.left: Optional["BSTNode"] = None
        self.right: Optional["BSTNode"] = None


class CourseBST:
    """依 (星期, 開始時間, 代碼) 建立之二元搜尋樹，支援空堂區間搜尋與推薦。"""

    def __init__(self):
        self.root: Optional[BSTNode] = None

    def insert(self, course: Course) -> None:
        self.root = self._insert_rec(self.root, course)

    def _insert_rec(self, node: Optional[BSTNode], course: Course) -> BSTNode:
        if node is None:
            return BSTNode(course)
        key = (course.day, course.start_min, course.code)
        if key < node.key:
            node.left = self._insert_rec(node.left, course)
        elif key > node.key:
            node.right = self._insert_rec(node.right, course)
        else:
            node.course = course
        return node

    def search(self, day: int, start_min: int, code: str) -> Optional[Course]:
        target = (day, start_min, code)
        curr = self.root
        while curr is not None:
            if target == curr.key:
                return curr.course
            elif target < curr.key:
                curr = curr.left
            else:
                curr = curr.right
        return None

    def delete(self, day: int, start_min: int, code: str) -> None:
        self.root = self._delete_rec(self.root, (day, start_min, code))

    def _delete_rec(self, node: Optional[BSTNode], target: Tuple[int, int, str]) -> Optional[BSTNode]:
        if node is None:
            return None
        if target < node.key:
            node.left = self._delete_rec(node.left, target)
        elif target > node.key:
            node.right = self._delete_rec(node.right, target)
        else:
            if node.left is None:
                return node.right
            if node.right is None:
                return node.left
            successor = self._min_node(node.right)
            node.course = successor.course
            node.key = successor.key
            node.right = self._delete_rec(node.right, successor.key)
        return node

    def _min_node(self, node: BSTNode) -> BSTNode:
        curr = node
        while curr.left is not None:
            curr = curr.left
        return curr

    def inorder_traversal(self) -> List[Course]:
        """中序遍歷（依時間先後輸出所有課程）：O(N)。"""
        result: List[Course] = []
        self._inorder_rec(self.root, result)
        return result

    def _inorder_rec(self, node: Optional[BSTNode], result: List[Course]) -> None:
        if node is None:
            return
        self._inorder_rec(node.left, result)
        result.append(node.course)
        self._inorder_rec(node.right, result)

    def search_free_slot_courses(
        self,
        day: int,
        free_start_min: int,
        free_end_min: int,
        enrolled_list: EnrolledLinkedList,
    ) -> List[Course]:
        """
        區間剪枝搜尋（Range Pruning Search）：
        找出指定星期 day 內，完整落於 [free_start_min, free_end_min] 且不與已選課表衝堂的課程。
        """
        candidates: List[Course] = []
        self._range_search_rec(self.root, day, free_start_min, free_end_min, enrolled_list, candidates)
        return candidates

    def _range_search_rec(
        self,
        node: Optional[BSTNode],
        day: int,
        free_start: int,
        free_end: int,
        enrolled_list: EnrolledLinkedList,
        candidates: List[Course],
    ) -> None:
        if node is None:
            return

        # 剪枝：若目前節點星期大於目標，或同日但開始時間已超過空堂結束時間，不需往右子樹搜尋
        if node.course.day > day or (node.course.day == day and node.course.start_min >= free_end):
            self._range_search_rec(node.left, day, free_start, free_end, enrolled_list, candidates)
            return

        # 剪枝：若目前節點星期小於目標，或同日但開始時間早於空堂起始時間，不需往左子樹搜尋
        if node.course.day < day or (node.course.day == day and node.course.start_min < free_start):
            self._range_search_rec(node.right, day, free_start, free_end, enrolled_list, candidates)
            return

        self._range_search_rec(node.left, day, free_start, free_end, enrolled_list, candidates)

        # 檢查課程結束時間是否也在空堂範圍內，且未選、不衝堂
        c = node.course
        if c.day == day and c.start_min >= free_start and c.end_min <= free_end:
            if enrolled_list.search(c.code) is None:
                has_conflict = False
                curr_enrolled = enrolled_list.head
                while curr_enrolled is not None:
                    if c.overlaps_with(curr_enrolled.course):
                        has_conflict = True
                        break
                    curr_enrolled = curr_enrolled.next
                if not has_conflict:
                    candidates.append(c)

        self._range_search_rec(node.right, day, free_start, free_end, enrolled_list, candidates)


# ==============================================================================
# [組員 2 - Tech Lead] 衝堂偵測引擎：Graph（純鏈結串列鄰接串列 + BFS）
# 複雜度：新增節點/邊 O(1)、刪除邊 O(E)、刪除節點 O(V+E)、查詢鄰居 O(deg(v))、BFS O(V+E)
# ==============================================================================
class EdgeNode:
    """鄰接邊節點。"""

    def __init__(self, to_code: str, next_edge: Optional["EdgeNode"] = None):
        self.to_code = to_code
        self.next = next_edge


class VertexNode:
    """圖形頂點節點。"""

    def __init__(self, code: str, next_vertex: Optional["VertexNode"] = None):
        self.code = code
        self.edges: Optional[EdgeNode] = None
        self.next = next_vertex


class _BFSQueueNode:
    def __init__(self, code: str, next_node: Optional["_BFSQueueNode"] = None):
        self.code = code
        self.next = next_node


class _BFSQueue:
    """供 Graph BFS 使用之輕量鏈結佇列（不使用內建 deque）。"""

    def __init__(self):
        self.head: Optional[_BFSQueueNode] = None
        self.tail: Optional[_BFSQueueNode] = None

    def enqueue(self, code: str) -> None:
        node = _BFSQueueNode(code)
        if self.tail is None:
            self.head = node
            self.tail = node
        else:
            self.tail.next = node
            self.tail = node

    def dequeue(self) -> Optional[str]:
        if self.head is None:
            return None
        val = self.head.code
        self.head = self.head.next
        if self.head is None:
            self.tail = None
        return val

    def is_empty(self) -> bool:
        return self.head is None


class ConflictGraph:
    """無向時間衝突圖（完全不使用內建 dict / set）。"""

    def __init__(self):
        self.vertices_head: Optional[VertexNode] = None
        self.vertex_index = CustomHashTable(32)  # O(1) 定位頂點指標

    def clear(self) -> None:
        self.vertices_head = None
        self.vertex_index = CustomHashTable(32)

    def add_vertex(self, code: str) -> VertexNode:
        """新增節點：O(1)。"""
        existing = self.vertex_index.search(code)
        if existing is not None:
            return existing
        v_node = VertexNode(code, self.vertices_head)
        self.vertices_head = v_node
        self.vertex_index.insert(code, v_node)
        return v_node

    def add_edge(self, code_a: str, code_b: str) -> None:
        """新增無向衝突邊：O(1)。"""
        va = self.add_vertex(code_a)
        vb = self.add_vertex(code_b)
        if not self._has_edge(va, code_b):
            va.edges = EdgeNode(code_b, va.edges)
        if not self._has_edge(vb, code_a):
            vb.edges = EdgeNode(code_a, vb.edges)

    def _has_edge(self, v_node: VertexNode, target_code: str) -> bool:
        e = v_node.edges
        while e is not None:
            if e.to_code == target_code:
                return True
            e = e.next
        return False

    def remove_edge(self, code_a: str, code_b: str) -> None:
        """刪除無向邊：O(E)。"""
        va = self.vertex_index.search(code_a)
        vb = self.vertex_index.search(code_b)
        if va is not None:
            va.edges = self._unlink_edge(va.edges, code_b)
        if vb is not None:
            vb.edges = self._unlink_edge(vb.edges, code_a)

    def _unlink_edge(self, head: Optional[EdgeNode], target: str) -> Optional[EdgeNode]:
        curr = head
        prev: Optional[EdgeNode] = None
        while curr is not None:
            if curr.to_code == target:
                if prev is None:
                    return curr.next
                prev.next = curr.next
                return head
            prev = curr
            curr = curr.next
        return head

    def remove_vertex(self, code: str) -> None:
        """刪除節點及所有相連邊：O(V + E)。"""
        v_curr = self.vertices_head
        v_prev: Optional[VertexNode] = None
        while v_curr is not None:
            if v_curr.code != code:
                v_curr.edges = self._unlink_edge(v_curr.edges, code)
                v_prev = v_curr
            else:
                if v_prev is None:
                    self.vertices_head = v_curr.next
                else:
                    v_prev.next = v_curr.next
            v_curr = v_curr.next
        self.vertex_index.delete(code)

    def get_neighbors(self, code: str) -> List[str]:
        """查詢鄰居（衝堂對象）：O(deg(v))。"""
        v_node = self.vertex_index.search(code)
        if v_node is None:
            return []
        neighbors: List[str] = []
        e = v_node.edges
        while e is not None:
            neighbors.append(e.to_code)
            e = e.next
        return neighbors

    def build_from_sorted_courses(self, sorted_courses: List[Course]) -> None:
        """利用已排序課表建立衝突圖（掃描線剪枝優化）。"""
        self.clear()
        n = len(sorted_courses)
        for i in range(n):
            self.add_vertex(sorted_courses[i].code)

        for i in range(n):
            curr = sorted_courses[i]
            for j in range(i + 1, n):
                nxt = sorted_courses[j]
                if nxt.day != curr.day or nxt.start_min >= curr.end_min:
                    break
                if curr.overlaps_with(nxt):
                    self.add_edge(curr.code, nxt.code)

    def get_conflict_clusters_bfs(self) -> List[List[str]]:
        """使用 BFS 找出所有連通衝堂群組：O(V + E)。"""
        visited = CustomHashTable(32)
        clusters: List[List[str]] = []

        v_curr = self.vertices_head
        while v_curr is not None:
            if v_curr.edges is not None and visited.search(v_curr.code) is None:
                cluster: List[str] = []
                q = _BFSQueue()
                q.enqueue(v_curr.code)
                visited.insert(v_curr.code, True)

                while not q.is_empty():
                    curr_code = q.dequeue()
                    cluster.append(curr_code)
                    node_obj = self.vertex_index.search(curr_code)
                    e = node_obj.edges if node_obj is not None else None
                    while e is not None:
                        if visited.search(e.to_code) is None:
                            visited.insert(e.to_code, True)
                            q.enqueue(e.to_code)
                        e = e.next
                clusters.append(cluster)
            v_curr = v_curr.next
        return clusters


# ==============================================================================
# [組員 1 & 組員 3] 效能基準測試（Benchmark：1,000 筆 & 5,000 筆 vs 內建容器）
# ==============================================================================
def run_benchmarks() -> None:
    print("=" * 72)
    print("  [Benchmark 效能基準測試] 自實作資料結構 vs Python 內建容器")
    print("=" * 72)

    for n in [1000, 5000]:
        test_courses: List[Course] = []
        for i in range(n):
            code = f"CRS{i:05d}"
            day = (i % 5) + 1
            p_start = (i % 8) + 1
            c = Course(
                code=code,
                name=f"測試課程_{i}",
                dept="資工系",
                category="選修",
                priority=(i % 4) + 1,
                credits=(i % 3) + 1,
                teacher="教師",
                room="教室",
                day=day,
                periods=[p_start, p_start + 1],
            )
            test_courses.append(c)

        query_keys = [test_courses[random.randint(0, n - 1)].code for _ in range(1000)]

        # 1. Hash Table vs 內建 dict
        t0 = time.perf_counter()
        custom_ht = CustomHashTable(capacity=16)
        for c in test_courses:
            custom_ht.insert(c.code, c)
        for qk in query_keys:
            custom_ht.search(qk)
        t_custom_ht = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        builtin_dict = {}
        for c in test_courses:
            builtin_dict[c.code] = c
        for qk in query_keys:
            _ = builtin_dict.get(qk)
        t_builtin_dict = (time.perf_counter() - t0) * 1000

        # 2. Merge Sort vs 內建 sorted()
        shuffled = [c for c in test_courses]
        random.shuffle(shuffled)

        t0 = time.perf_counter()
        _ = merge_sort_courses(shuffled, mode="time")
        t_custom_sort = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        _ = sorted(shuffled, key=lambda x: (x.day, x.start_min, x.end_min, x.code))
        t_builtin_sort = (time.perf_counter() - t0) * 1000

        print(f"資料規模 N = {n} 筆：")
        print(f"  1. [組員1 Hash Table]   自寫鏈結雜湊: {t_custom_ht:7.3f} ms | 內建 dict:     {t_builtin_dict:7.3f} ms")
        print(f"  2. [組員3 Merge Sort]   自寫合併排序: {t_custom_sort:7.3f} ms | 內建 sorted(): {t_builtin_sort:7.3f} ms")
        print("-" * 72)


# ==============================================================================
# 主系統整合中心（串接 6 位組員之資料結構模組）
# ==============================================================================
class IntegratedCourseSystem:
    def __init__(self):
        self.db_table = CustomHashTable(16)         # 組員 1：全校開課資料庫
        self.conflict_graph = ConflictGraph()       # 組員 2：時間衝突圖
        self.enrolled_list = EnrolledLinkedList()   # 組員 4：個人已選鏈結串列
        self.undo_stack = UndoStack()               # 組員 5-A：復原操作堆疊
        self.waitlist_queue = WaitlistQueue()       # 組員 5-B：熱門課程候補佇列
        self.time_bst = CourseBST()                 # 組員 6：空堂時段二元搜尋樹
        self._init_sample_courses()

    def _init_sample_courses(self) -> None:
        samples = [
            Course("C101", "資料結構", "資工系", "必修", 1, 3, "陳老師", "資訊館 302", 1, [2, 3, 4], 50, 42),
            Course("C102", "線性代數", "資工系", "必修", 1, 3, "林老師", "工學院 201", 1, [3, 4], 50, 48),
            Course("C103", "演算法設計", "資工系", "必修", 1, 3, "王老師", "資訊館 401", 2, [2, 3, 4], 50, 35),
            Course("C104", "資料庫系統", "資工系", "選修", 2, 3, "張老師", "資訊館 305", 2, [6, 7], 40, 40),
            Course("C105", "作業系統", "資工系", "必修", 1, 3, "李老師", "資訊館 302", 3, [2, 3, 4], 50, 45),
            Course("G201", "科技與倫理", "博雅中心", "通識", 3, 2, "黃老師", "人文大樓 105", 3, [6, 7], 60, 52),
            Course("G202", "AI 應用導論", "博雅中心", "通識", 3, 2, "吳老師", "圖資大樓 202", 3, [7, 8], 60, 58),
            Course("G203", "創新創業實務", "博雅中心", "通識", 3, 2, "周老師", "管理大樓 301", 3, [8, 9], 60, 30),
            Course("C106", "物件導向程式設計", "資工系", "選修", 2, 3, "鄭老師", "資訊館 204", 4, [2, 3, 4], 45, 45),
            Course("P301", "羽球體育", "體育室", "必修", 1, 0, "劉教練", "綜合體育館", 4, [6, 7], 40, 38),
            Course("C107", "計算機網路", "資工系", "必修", 1, 3, "許老師", "資訊館 401", 5, [2, 3, 4], 50, 44),
            Course("S401", "熱音社團練", "學務處", "社團", 4, 0, "社團幹部", "活動中心 B1", 5, [3, 4, 5], 30, 18),
        ]
        for c in samples:
            self.db_table.insert(c.code, c)
            self.time_bst.insert(c)

        # 預設已選 4 門課
        for init_code in ["C101", "C103", "G201", "P301"]:
            course = self.db_table.search(init_code)
            if course is not None:
                self.enrolled_list.insert_tail(course)

        # 預設候補佇列示範資料
        self.waitlist_queue.enqueue("王小明 (同學)", "C104")

    def enroll_course(self, code: str, record_undo: bool = True) -> None:
        course = self.db_table.search(code)
        if course is None:
            return
        if self.enrolled_list.insert_tail(course):
            if record_undo:
                self.undo_stack.push("ADD", code)

    def drop_course(self, code: str, record_undo: bool = True) -> None:
        dropped = self.enrolled_list.delete(code)
        if dropped is not None and record_undo:
            self.undo_stack.push("DROP", code)

    def undo_last_action(self) -> None:
        """組員 5 Stack：彈出最近一次加選或退選操作並反向還原。"""
        last = self.undo_stack.pop()
        if last is None:
            return
        action, code = last
        if action == "ADD":
            self.drop_course(code, record_undo=False)
        elif action == "DROP":
            self.enroll_course(code, record_undo=False)

    def join_waitlist(self, code: str) -> None:
        """組員 5 Queue：將目前使用者加入候補佇列尾端（Enqueue）。"""
        course = self.db_table.search(code)
        if course is not None and self.enrolled_list.search(code) is None:
            self.waitlist_queue.enqueue("我 (目前使用者)", code)

    def process_next_waitlist(self) -> None:
        """組員 5 Queue：模擬有人退選，從佇列前端（Dequeue）依序遞補。"""
        front_item = self.waitlist_queue.dequeue()
        if front_item is None:
            return
        student_name, code = front_item
        if student_name == "我 (目前使用者)":
            self.enroll_course(code, record_undo=True)

    def auto_resolve_conflicts(self) -> None:
        """組員 2 + 組員 3：貪婪區間排程，依結束時間排序並保留最多門無衝堂課程。"""
        current_courses = self.enrolled_list.traverse()
        sorted_by_end = merge_sort_courses(current_courses, mode="end")

        kept_list = EnrolledLinkedList()
        last_end_by_day = [0] * 8
        for c in sorted_by_end:
            if c.start_min >= last_end_by_day[c.day]:
                kept_list.insert_tail(c)
                last_end_by_day[c.day] = c.end_min

        self.enrolled_list = kept_list
        self.undo_stack = UndoStack()

    def build_state_payload(
        self,
        query: str = "",
        sort_mode: str = "time",
        free_day: int = 3,
        free_start_p: int = 5,
        free_end_p: int = 10,
    ) -> dict:
        query = query.strip()
        hash_debug = None
        if query:
            found, bucket_idx, steps = self.db_table.search_with_debug(query.upper())
            if found is not None:
                hash_debug = {
                    "code": found.code,
                    "bucket": bucket_idx,
                    "steps": steps,
                    "capacity": self.db_table.capacity,
                }

        # 1. 取得全部開課並過濾
        all_courses: List[Course] = self.db_table.values()
        filtered: List[Course] = []
        q_lower = query.lower()
        for c in all_courses:
            if query:
                if (
                    q_lower not in c.code.lower()
                    and q_lower not in c.name.lower()
                    and q_lower not in c.teacher.lower()
                ):
                    continue
            filtered.append(c)

        # 2. 組員 3：使用自寫 Merge Sort 排序開課清單
        sorted_catalog = merge_sort_courses(filtered, mode=sort_mode)

        # 3. 組員 4：從 Linked List 取得個人已選課程（保留鏈結串接順序與排序後課表）
        linked_courses = self.enrolled_list.traverse()
        sorted_enrolled = merge_sort_courses(linked_courses, mode="time")

        # 4. 組員 2：建立 Conflict Graph 並執行 BFS 連通群組偵測
        self.conflict_graph.build_from_sorted_courses(sorted_enrolled)
        clusters = self.conflict_graph.get_conflict_clusters_bfs()

        adj_list_display = []
        v_curr = self.conflict_graph.vertices_head
        while v_curr is not None:
            neighbors = self.conflict_graph.get_neighbors(v_curr.code)
            if len(neighbors) > 0:
                adj_list_display.append({"node": v_curr.code, "neighbors": neighbors})
            v_curr = v_curr.next

        # 5. 組員 6：使用 BST 搜尋指定空堂區間之可選無衝堂課程
        f_start_min = time_str_to_minutes(PERIOD_TIMES[free_start_p][0])
        f_end_min = time_str_to_minutes(PERIOD_TIMES[free_end_p][1])
        bst_recommendations = self.time_bst.search_free_slot_courses(
            free_day, f_start_min, f_end_min, self.enrolled_list
        )

        # 組裝開課清單前端資料
        catalog_data = []
        for c in sorted_catalog:
            d = c.to_dict()
            d["enrolled"] = self.enrolled_list.search(c.code) is not None
            d["isFull"] = c.enrolled_count >= c.capacity
            conflicts = []
            for ec in sorted_enrolled:
                if ec.code != c.code and c.overlaps_with(ec):
                    conflicts.append(ec.code)
            d["conflictsWith"] = conflicts
            catalog_data.append(d)

        total_credits = sum(c.credits for c in linked_courses)

        return {
            "catalog": catalog_data,
            "enrolledSorted": [c.to_dict() for c in sorted_enrolled],
            "linkedListChain": [c.code for c in linked_courses],
            "totalCredits": total_credits,
            "hashStats": {
                "size": self.db_table.size,
                "capacity": self.db_table.capacity,
            },
            "hashDebug": hash_debug,
            "graphAdj": adj_list_display,
            "conflictClusters": clusters,
            "undoStack": self.undo_stack.to_list(),
            "waitlistQueue": self.waitlist_queue.to_list(),
            "bstRecommendations": [c.to_dict() for c in bst_recommendations],
        }


SYSTEM = IntegratedCourseSystem()


# ==============================================================================
# 網頁視覺化展示介面（整合 6 組員模組操作）
# ==============================================================================
HTML_PAGE = r"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<title>#12 課程／活動衝堂檢查系統（6種核心資料結構整合版）</title>
<style>
  * { box-sizing: border-box; font-family: "Microsoft JhengHei", "Segoe UI", sans-serif; }
  body { margin: 0; background: #f1f5f9; color: #0f172a; }
  header {
    background: linear-gradient(135deg, #0f3d68 0%, #1e6091 100%);
    color: #fff; padding: 14px 22px; display: flex; justify-content: space-between; align-items: center;
  }
  header h1 { margin: 0; font-size: 19px; }
  header .sub { font-size: 12px; opacity: 0.88; margin-top: 3px; }
  .pill { background: rgba(255,255,255,0.18); padding: 5px 12px; border-radius: 16px; font-size: 13px; font-weight: bold; }
  .grid-main {
    display: grid; grid-template-columns: 1.15fr 1fr; gap: 14px;
    padding: 14px 18px; max-width: 1520px; margin: 0 auto;
  }
  .card {
    background: #fff; border-radius: 8px; padding: 14px;
    border: 1px solid #cbd5e1; box-shadow: 0 1px 3px rgba(0,0,0,0.06); margin-bottom: 14px;
  }
  .card-title {
    font-size: 15px; font-weight: bold; color: #0f3d68;
    border-bottom: 2px solid #e2e8f0; padding-bottom: 6px; margin: 0 0 10px 0;
    display: flex; justify-content: space-between; align-items: center;
  }
  .toolbar { display: flex; gap: 8px; margin-bottom: 10px; flex-wrap: wrap; }
  input, select { padding: 6px 9px; border: 1px solid #cbd5e1; border-radius: 5px; font-size: 13px; }
  input { flex: 1; }
  button {
    cursor: pointer; border: none; border-radius: 5px; padding: 5px 10px;
    font-size: 12px; font-weight: bold;
  }
  .btn-primary { background: #1d6fa5; color: #fff; }
  .btn-warn { background: #d97706; color: #fff; }
  .btn-danger { background: #dc2626; color: #fff; }
  .btn-success { background: #059669; color: #fff; }
  .btn-purple { background: #7c3aed; color: #fff; }
  table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
  th { background: #f8fafc; padding: 7px; text-align: left; border-bottom: 2px solid #cbd5e1; }
  td { padding: 7px; border-bottom: 1px solid #e2e8f0; }
  .tag { padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; }
  .t-1 { background: #fee2e2; color: #b91c1c; }
  .t-2 { background: #dbeafe; color: #1d4ed8; }
  .t-3 { background: #dcfce7; color: #15803d; }
  .t-4 { background: #fef3c7; color: #b45309; }
  .info-box {
    background: #eff6ff; border-left: 4px solid #2563eb; padding: 7px 10px;
    font-size: 12px; margin-bottom: 8px; border-radius: 4px;
  }
  .chain-box {
    background: #f8fafc; border: 1px dashed #94a3b8; padding: 8px;
    border-radius: 5px; font-family: Consolas, monospace; font-size: 12px; word-break: break-all;
  }
  .timetable th, .timetable td { border: 1px solid #cbd5e1; text-align: center; padding: 4px; width: 17%; }
  .timetable th:first-child, .timetable td:first-child { width: 15%; background: #f8fafc; font-weight: bold; }
  .c-ok { background: #e0f2fe; border: 1px solid #38bdf8; color: #0369a1; border-radius: 4px; padding: 2px; margin: 1px 0; font-weight: bold; }
  .c-bad { background: #fee2e2; border: 1px solid #f87171; color: #b91c1c; border-radius: 4px; padding: 2px; margin: 1px 0; font-weight: bold; }
  .two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .badge-list { font-family: Consolas, monospace; font-size: 12px; background: #fffbeb; border: 1px solid #fde68a; padding: 6px; border-radius: 4px; margin-top: 6px; }
  @media (max-width: 1100px) { .grid-main, .two-col { grid-template-columns: 1fr; } }
</style>
</head>
<body>

<header>
  <div>
    <h1>#12 課程／活動衝堂檢查系統（6 大核心資料結構整合專題）</h1>
    <div class="sub">Hash Table ＋ Graph (Adjacency List) ＋ Merge Sort ＋ Linked List ＋ Stack / Queue ＋ BST</div>
  </div>
  <div style="display:flex; gap:10px;">
    <div class="pill" id="htStat">Hash Table: 0/16</div>
    <div class="pill" id="credStat">已選學分：0</div>
  </div>
</header>

<div class="grid-main">
  <!-- 左半部：組員1 HashTable + 組員3 MergeSort + 組員4 LinkedList + 組員5 Stack/Queue -->
  <div>
    <div class="card">
      <div class="card-title">
        <span>[組員1 Hash Table &amp; 組員3 Merge Sort] 開課查詢與排序</span>
      </div>
      <div class="toolbar">
        <input type="text" id="qInput" placeholder="輸入課程代號（如 C101）測試 Hash Table O(1) 查詢..." oninput="loadState()">
        <select id="sortSel" onchange="loadState()">
          <option value="time">Merge Sort：星期／節次先後</option>
          <option value="credits">Merge Sort：學分數（高→低）</option>
          <option value="priority">Merge Sort：優先度（必修優先）</option>
        </select>
      </div>
      <div id="hashBox" class="info-box" style="display:none;"></div>
      <table>
        <thead>
          <tr><th>代號</th><th>課程名稱</th><th>類別</th><th>學分</th><th>人數</th><th>時間</th><th>操作</th></tr>
        </thead>
        <tbody id="catBody"></tbody>
      </table>
    </div>

    <div class="card">
      <div class="card-title">
        <span>[組員4 Linked List] 個人已選清單節點串接狀態</span>
      </div>
      <div class="chain-box" id="llChainBox">HEAD -&gt; NULL</div>
    </div>

    <div class="two-col">
      <div class="card">
        <div class="card-title">
          <span>[組員5-A Stack] 加退選復原</span>
          <button class="btn-purple" onclick="postAction('/api/undo', {})">Undo 上一步</button>
        </div>
        <div style="font-size:12px; color:#475569;">LIFO 堆疊頂端為最近一次操作：</div>
        <div class="badge-list" id="stackBox">堆疊為空</div>
      </div>

      <div class="card">
        <div class="card-title">
          <span>[組員5-B Queue] 額滿候補遞補</span>
          <button class="btn-success" onclick="postAction('/api/dequeue', {})">Dequeue 遞補</button>
        </div>
        <div style="font-size:12px; color:#475569;">FIFO 佇列依排隊順序遞補額滿課程：</div>
        <div class="badge-list" id="queueBox">候補佇列為空</div>
      </div>
    </div>
  </div>

  <!-- 右半部：組員2 Graph 衝堂偵測 + 組員6 BST 空堂時段搜尋 -->
  <div>
    <div class="card">
      <div class="card-title">
        <span>[組員2 Graph] 週課表與時間衝突關係圖（Adjacency List + BFS）</span>
        <button class="btn-success" onclick="postAction('/api/resolve', {})">一鍵排除衝堂</button>
      </div>
      <div id="conflictBanner" style="margin-bottom:8px;"></div>
      <table class="timetable">
        <thead>
          <tr><th>節次</th><th>週一</th><th>週二</th><th>週三</th><th>週四</th><th>週五</th></tr>
        </thead>
        <tbody id="ttBody"></tbody>
      </table>
      <div class="badge-list" id="graphBox"></div>
    </div>

    <div class="card">
      <div class="card-title">
        <span>[組員6 BST] 空堂時段區間搜尋與可選課程推薦</span>
      </div>
      <div class="toolbar">
        <select id="freeDay" onchange="loadState()">
          <option value="1">週一</option>
          <option value="2">週二</option>
          <option value="3" selected>週三</option>
          <option value="4">週四</option>
          <option value="5">週五</option>
        </select>
        <select id="freeStart" onchange="loadState()">
          <option value="1">第1節 (08:10)</option>
          <option value="2">第2節 (09:10)</option>
          <option value="5" selected>第5節 (13:30)</option>
          <option value="6">第6節 (14:30)</option>
        </select>
        <span style="align-self:center;">至</span>
        <select id="freeEnd" onchange="loadState()">
          <option value="4">第4節 (12:00)</option>
          <option value="8">第8節 (17:20)</option>
          <option value="10" selected>第10節 (19:20)</option>
        </select>
      </div>
      <div id="bstBox" style="font-size:13px;"></div>
    </div>
  </div>
</div>

<script>
const P_NAMES = {
  1:"第1節 08:10", 2:"第2節 09:10", 3:"第3節 10:10", 4:"第4節 11:10",
  5:"第5節 13:30", 6:"第6節 14:30", 7:"第7節 15:30", 8:"第8節 16:30",
  9:"第9節 17:30", 10:"第10節 18:30"
};

async function loadState() {
  const q = encodeURIComponent(document.getElementById("qInput").value);
  const sort = document.getElementById("sortSel").value;
  const fDay = document.getElementById("freeDay").value;
  const fStart = document.getElementById("freeStart").value;
  const fEnd = document.getElementById("freeEnd").value;
  const res = await fetch(`/api/state?q=${q}&sort=${sort}&fDay=${fDay}&fStart=${fStart}&fEnd=${fEnd}`);
  const data = await res.json();
  render(data);
}

async function postAction(url, bodyObj) {
  await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(bodyObj)
  });
  loadState();
}

function render(d) {
  document.getElementById("htStat").innerText = `Hash Table: ${d.hashStats.size}/${d.hashStats.capacity}`;
  document.getElementById("credStat").innerText = `已選學分：${d.totalCredits}`;

  // 組員 1 Hash Table 命中資訊
  const hb = document.getElementById("hashBox");
  if (d.hashDebug) {
    hb.style.display = "block";
    hb.innerHTML = `<strong>Hash Table 命中：</strong>代號 <code>${d.hashDebug.code}</code> 位於 Bucket <strong>#${d.hashDebug.bucket}</strong>（鏈結探測步數：${d.hashDebug.steps}）`;
  } else {
    hb.style.display = "none";
  }

  // 開課表
  const cb = document.getElementById("catBody");
  cb.innerHTML = "";
  d.catalog.forEach(c => {
    let btn = "";
    if (c.enrolled) {
      btn = `<button class="btn-danger" onclick="postAction('/api/drop', {code:'${c.code}'})">退選</button>`;
    } else if (c.isFull) {
      btn = `<button class="btn-warn" onclick="postAction('/api/waitlist', {code:'${c.code}'})">額滿候補</button>`;
    } else if (c.conflictsWith.length > 0) {
      btn = `<button class="btn-warn" onclick="postAction('/api/enroll', {code:'${c.code}'})">⚠ 衝堂加選</button>`;
    } else {
      btn = `<button class="btn-primary" onclick="postAction('/api/enroll', {code:'${c.code}'})">＋ 加選</button>`;
    }
    cb.innerHTML += `
      <tr>
        <td><strong>${c.code}</strong></td>
        <td>${c.name}</td>
        <td><span class="tag t-${c.priority}">${c.category}</span></td>
        <td>${c.credits}</td>
        <td>${c.enrolledCount}/${c.capacity}</td>
        <td>${c.timeLabel}</td>
        <td>${btn}</td>
      </tr>`;
  });

  // 組員 4 Linked List 鏈結視覺化
  const llBox = document.getElementById("llChainBox");
  llBox.innerText = d.linkedListChain.length === 0
    ? "HEAD -> NULL"
    : "HEAD -> " + d.linkedListChain.map(x => `[${x}]`).join(" -> ") + " -> NULL";

  // 組員 5 Stack & Queue
  const sb = document.getElementById("stackBox");
  sb.innerHTML = d.undoStack.length === 0
    ? "堆疊為空（尚無加退選紀錄）"
    : d.undoStack.map((item, idx) => `${idx === 0 ? "[TOP] " : "      "}${item.action === "ADD" ? "加選" : "退選"} ${item.code}`).join("<br>");

  const qb = document.getElementById("queueBox");
  qb.innerHTML = d.waitlistQueue.length === 0
    ? "候補佇列為空"
    : d.waitlistQueue.map((item, idx) => `${idx === 0 ? "[FRONT] " : "        "}${item.student} 等候 ${item.code}`).join("<br>");

  // 組員 2 Graph 衝堂狀態與週課表
  const banner = document.getElementById("conflictBanner");
  if (d.conflictClusters.length > 0) {
    banner.innerHTML = `<div style="background:#fef2f2;border-left:4px solid #dc2626;padding:7px;font-size:12.5px;color:#991b1b;"><strong>⚠ Graph 偵測到 ${d.conflictClusters.length} 個衝堂連通群組！</strong></div>`;
  } else {
    banner.innerHTML = `<div style="background:#ecfdf5;border-left:4px solid #059669;padding:7px;font-size:12.5px;color:#065f46;"><strong>✓ 無衝堂邊：</strong>目前課表無任何時間衝突。</div>`;
  }

  const tt = document.getElementById("ttBody");
  tt.innerHTML = "";
  for (let p = 1; p <= 10; p++) {
    let row = `<td>${P_NAMES[p]}</td>`;
    for (let day = 1; day <= 5; day++) {
      const hits = d.enrolledSorted.filter(c => c.day === day && c.periods.includes(p));
      if (hits.length === 0) row += "<td></td>";
      else {
        const cls = hits.length > 1 ? "c-bad" : "c-ok";
        row += "<td>" + hits.map(h => `<div class="${cls}">${h.code} ${h.name}</div>`).join("") + "</td>";
      }
    }
    tt.innerHTML += `<tr>${row}</tr>`;
  }

  const gb = document.getElementById("graphBox");
  if (d.graphAdj.length === 0) {
    gb.innerHTML = "Adjacency List：無衝突邊（Edges = 0）";
  } else {
    let gHtml = "<strong>Adjacency List 衝突邊：</strong><br>";
    d.graphAdj.forEach(item => {
      gHtml += `節點 [${item.node}] &lt;--&gt; [${item.neighbors.join(", ")}]<br>`;
    });
    gHtml += "<strong>BFS 連通衝堂群組：</strong> " + d.conflictClusters.map(c => `(${c.join(" - ")})`).join("；");
    gb.innerHTML = gHtml;
  }

  // 組員 6 BST 空堂推薦
  const bstDiv = document.getElementById("bstBox");
  if (d.bstRecommendations.length === 0) {
    bstDiv.innerHTML = "<span style='color:#64748b;'>該空堂時段內無其他可選且不衝堂之課程。</span>";
  } else {
    bstDiv.innerHTML = "<strong>BST 區間搜尋推薦可選課程：</strong><ul style='margin:6px 0;padding-left:18px;'>" +
      d.bstRecommendations.map(c => `<li><strong>[${c.code}] ${c.name}</strong>（${c.timeLabel}，${c.credits} 學分）</li>`).join("") +
      "</ul>";
  }
}

loadState();
</script>
</body>
</html>
"""


class ReusableHTTPServer(HTTPServer):
    allow_reuse_address = True


class AppHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _json_response(self, payload: dict) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            raw = HTML_PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        elif parsed.path == "/api/state":
            qs = parse_qs(parsed.query)
            q = qs.get("q", [""])[0]
            sort_mode = qs.get("sort", ["time"])[0]
            f_day = int(qs.get("fDay", ["3"])[0])
            f_start = int(qs.get("fStart", ["5"])[0])
            f_end = int(qs.get("fEnd", ["10"])[0])
            self._json_response(SYSTEM.build_state_payload(q, sort_mode, f_day, f_start, f_end))
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}
        code = body.get("code", "")

        if self.path == "/api/enroll":
            SYSTEM.enroll_course(code)
        elif self.path == "/api/drop":
            SYSTEM.drop_course(code)
        elif self.path == "/api/undo":
            SYSTEM.undo_last_action()
        elif self.path == "/api/waitlist":
            SYSTEM.join_waitlist(code)
        elif self.path == "/api/dequeue":
            SYSTEM.process_next_waitlist()
        elif self.path == "/api/resolve":
            SYSTEM.auto_resolve_conflicts()
        self._json_response({"ok": True})


def get_free_port(start: int = 8060) -> int:
    for p in range(start, start + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    return start


# ==============================================================================
# 執行入口：1. 輸出 Benchmark 數據至 Console  2. 啟動互動式網頁系統
# ==============================================================================
run_benchmarks()

port = get_free_port(8060)
url = f"http://127.0.0.1:{port}"
server = ReusableHTTPServer(("127.0.0.1", port), AppHandler)

print(f"\n系統網頁介面已啟動：{url}")
print("Demo 錄影完畢後，請點擊 Spyder Console 右上角的紅色停止按鈕（■）關閉伺服器。")

threading.Timer(0.8, lambda: webbrowser.open(url)).start()
server.serve_forever()