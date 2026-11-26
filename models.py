//統一的 Course 物件與純自製基礎陣列/節點（避開內建 list/dict 違規）
# models.py - 全組共用的資料格式與基礎底層結構（無任何外部套件）

class TimeSlot:
    """表示單一上課/活動時段，例如：週一 10:10 ~ 12:00"""
    def __init__(self, day: int, start_min: int, end_min: int):
        self.day = day              # 1=週一 ~ 7=週日
        self.start_min = start_min  # 從 00:00 起算的分鐘數，例如 10:10 -> 610
        self.end_min = end_min      # 例如 12:00 -> 720

    def overlaps_with(self, other: "TimeSlot") -> bool:
        """判斷兩個時段是否重疊（衝堂核心邏輯）"""
        if self.day != other.day:
            return False
        # 區間重疊條件：A開始 < B結束 且 B開始 < A結束
        return self.start_min < other.end_min and other.start_min < self.end_min

    def __str__(self):
        days = ("", "週一", "週二", "週三", "週四", "週五", "週六", "週日")
        sh, sm = divmod(self.start_min, 60)
        eh, em = divmod(self.end_min, 60)
        return f"{days[self.day]} {sh:02d}:{sm:02d}-{eh:02d}:{em:02d}"


class Course:
    """統一的課程/活動物件，所有組員的資料結構都存這個物件"""
    def __init__(self, course_id: str, name: str, credits: int, slot: TimeSlot):
        self.course_id = course_id  # 例如 "CS101" 或 "ACT05"
        self.name = name            # 例如 "資料結構"
        self.credits = credits      # 學分數（活動可設為 0）
        self.slot = slot            # TimeSlot 物件

    def is_conflict_with(self, other: "Course") -> bool:
        """檢查兩門課/活動是否時間衝堂"""
        return self.slot.overlaps_with(other.slot)

    def __str__(self):
        return f"[{self.course_id}] {self.name} ({self.credits}學分) | {self.slot}"


class CustomArray:
    """
    自製固定容量陣列包裝（供 Hash Table 桶子或 Graph 頂點表使用）
    避免直接拿 Python 內建動態 list 當作核心資料結構本體
    """
    def __init__(self, capacity: int):
        self.capacity = capacity
        self._data = [None] * capacity  # 模擬底層連續記憶體空間

    def get(self, index: int):
        if index < 0 or index >= self.capacity:
            raise IndexError("索引超出自製陣列範圍")
        return self._data[index]

    def set(self, index: int, value):
        if index < 0 or index >= self.capacity:
            raise IndexError("索引超出自製陣列範圍")
        self._data[index] = value
