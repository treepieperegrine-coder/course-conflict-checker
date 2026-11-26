//[你的核心] 衝堂偵測引擎（自製 Graph 鄰接串列 + 衝堂查詢 + 無衝突建議）
# graph_engine.py - 組員 2 負責：衝堂偵測引擎（自製 Graph 鄰接串列）
from models import Course, CustomArray


class EdgeNode:
    """鄰接串列的邊節點：記錄與哪個頂點索引衝堂"""
    def __init__(self, target_idx: int, next_edge: "EdgeNode" = None):
        self.target_idx = target_idx
        self.next = next_edge


class VertexNode:
    """圖的頂點節點：存放課程物件與其衝堂鄰居鏈結串列"""
    def __init__(self, course: Course):
        self.course = course
        self.head_edge: EdgeNode = None  # 指向第一個衝堂課程的邊節點


class ConflictGraph:
    """
    無向衝突圖 (Conflict Graph)
    - 頂點 (Vertex): 課程 / 活動
    - 邊 (Edge): 兩門課程時間重疊（衝堂）
    """
    def __init__(self, max_courses: int = 6000):
        self.max_courses = max_courses
        self.vertices = CustomArray(max_courses)
        self.num_vertices = 0

    def _find_vertex_index(self, course_id: str) -> int:
        """根據 course_id 尋找頂點索引 | 時間複雜度: O(V)"""
        for i in range(self.num_vertices):
            v: VertexNode = self.vertices.get(i)
            if v is not None and v.course.course_id == course_id:
                return i
        return -1

    def _add_undirected_edge(self, idx_a: int, idx_b: int):
        """在 idx_a 與 idx_b 之間建立無向邊 | 時間複雜度: O(1)"""
        va: VertexNode = self.vertices.get(idx_a)
        vb: VertexNode = self.vertices.get(idx_b)
        va.head_edge = EdgeNode(idx_b, va.head_edge)
        vb.head_edge = EdgeNode(idx_a, vb.head_edge)

    def add_course(self, new_course: Course) -> bool:
        """
        新增課程頂點，並自動比對現有課程建立衝堂邊
        時間複雜度: O(V)（V 為目前圖中課程總數）
        """
        if self.num_vertices >= self.max_courses:
            return False
        if self._find_vertex_index(new_course.course_id) != -1:
            return False  # 已存在相同課程代碼

        new_idx = self.num_vertices
        self.vertices.set(new_idx, VertexNode(new_course))
        self.num_vertices += 1

        # 檢查新課程與所有既有課程是否衝堂，若有則連一條無向邊
        for i in range(new_idx):
            existing_v: VertexNode = self.vertices.get(i)
            if new_course.is_conflict_with(existing_v.course):
                self._add_undirected_edge(new_idx, i)

        return True

    def get_conflicts(self, course_id: str) -> list:
        """
        查詢指定課程的所有衝堂課程（僅回傳結果供介面顯示）
        時間複雜度: O(V + deg(v))，找到頂點後走訪鄰居僅需 O(deg(v))
        """
        idx = self._find_vertex_index(course_id)
        if idx == -1:
            return []

        result = []
        curr_edge = self.vertices.get(idx).head_edge
        while curr_edge is not None:
            neighbor_v: VertexNode = self.vertices.get(curr_edge.target_idx)
            result.append(neighbor_v.course)
            curr_edge = curr_edge.next
        return result

    def check_schedule_conflicts(self, selected_ids: list) -> list:
        """
        檢查一組已選課程 ID 清單中，有哪些成對衝堂
        時間複雜度: O(K * (V + E_local))，K 為已選課程數
        """
        conflicts = []
        n = len(selected_ids)
        for i in range(n):
            idx_a = self._find_vertex_index(selected_ids[i])
            if idx_a == -1:
                continue
            for j in range(i + 1, n):
                idx_b = self._find_vertex_index(selected_ids[j])
                if idx_b == -1:
                    continue
                # 檢查 idx_b 是否在 idx_a 的鄰接串列中
                curr = self.vertices.get(idx_a).head_edge
                while curr is not None:
                    if curr.target_idx == idx_b:
                        va = self.vertices.get(idx_a).course
                        vb = self.vertices.get(idx_b).course
                        conflicts.append((va, vb))
                        break
                    curr = curr.next
        return conflicts


# 單獨測試區塊（你上台 Demo 時也可以單獨跑這支檔案展示）
if __name__ == "__main__":
    g = ConflictGraph(max_courses=100)
    c1 = Course("EE201", "電路學", 3, TimeSlot(1, 610, 720))       # 週一 10:10-12:00
    c2 = Course("EE205", "資料結構", 3, TimeSlot(1, 670, 780))     # 週一 11:10-13:00 (衝堂!)
    c3 = Course("GE102", "社團博覽會", 0, TimeSlot(3, 810, 930))   # 週三 13:30-15:30 (不衝堂)

    g.add_course(c1)
    g.add_course(c2)
    g.add_course(c3)

    print("與資料結構衝堂的課程：")
    for c in g.get_conflicts("EE205"):
        print(" ->", c)
