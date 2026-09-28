"""Event templates S2 (T044, lane A). 10 disruption types, Vietnamese.

Types (spec US8 + data-model DynamicEvent + edge cases):
  rain, delay, drop_poi, add_req, tired, closure, time_change,
  traffic, budget, lost
Slots {poi}/{time}/{dish}/{amount} are filled from SEED_* lists
(seed POI names keep the template phase grounded in real data).
"""

from __future__ import annotations

EVENT_TYPES = (
    "rain", "delay", "drop_poi", "add_req", "tired",
    "closure", "time_change", "traffic", "budget", "lost",
)

SEED_POIS = ["Sơn Trà", "Mỹ Khê", "Cầu Rồng", "Bảo tàng Chăm", "Chợ Hàn", "Bà Nà"]
SEED_TIMES = ["14 giờ", "3 giờ chiều", "16:30", "tối nay", "sáng mai", "12 giờ trưa"]
SEED_DISHES = ["mì Quảng", "bánh xèo", "hải sản", "cao lầu", "bún chả cá"]
SEED_AMOUNTS = ["500 nghìn", "1 triệu", "200 nghìn", "2 triệu"]

TEMPLATES: dict[str, list[str]] = {
    "rain": [
        "trời mưa to quá, tìm chỗ trong nhà đi",
        "dự báo mưa {time}, đổi chỗ ngoài trời nhé",
        "mưa rồi, {poi} chắc ướt hết",
        "mưa {time} thì lịch chiều tính sao",
        "đang đi thì gặp mưa rào, có phương án khô ráo không",
        "mưa lớn quá không đi {poi} được",
    ],
    "delay": [
        "xe đến trễ 30 phút rồi",
        "tắc đường nên tới {poi} muộn hơn dự kiến",
        "chuyến đi bị delay, dời lịch {time} giúp",
        "đợi mãi chưa thấy xe, lịch có vỡ không",
        "đến muộn 1 tiếng, cắt bớt điểm nào",
    ],
    "drop_poi": [
        "tôi mệt, bỏ leo núi ở {poi}",
        "bỏ {poi} nhé, không hứng nữa",
        "skip điểm {poi}, đi thẳng ra biển",
        "hủy {poi} chiều nay, ở khách sạn nghỉ",
        "không đi {poi} nữa, thay chỗ khác",
    ],
    "add_req": [
        "thêm quán {dish} vào lịch tối nay",
        "muốn ghé {poi} buổi sáng, nhét vào giúp",
        "thêm yêu cầu: chỗ yên tĩnh để hẹn hò",
        "đi thêm chợ đêm nữa được không",
        "cho thêm 1 điểm check-in gần {poi}",
    ],
    "tired": [
        "tôi mệt quá, giảm cường độ đi",
        "đi bộ nhiều đuối rồi, thêm giờ nghỉ",
        "cả nhóm oải hết, lịch nhẹ lại nhé",
        "mệt, bỏ hoạt động tốn sức chiều nay",
        "hết sức rồi, về khách sạn sớm",
    ],
    "closure": [
        "{poi} đóng cửa hôm nay, thay điểm khác",
        "bảo tàng đóng cửa {time}, đổi lịch",
        "quán đóng cửa mất rồi, gợi ý quán khác",
        "điểm này tạm ngưng đón khách, kiểm tra giúp",
        "{poi} báo đóng cửa đột xuất",
    ],
    "time_change": [
        "đổi giờ đi thành {time} nhé",
        "đi sớm hơn 1 tiếng được không",
        "dời lịch {poi} sang sáng mai",
        "kết thúc muộn hơn {time} có sao không",
        "đổi khung giờ cả buổi chiều",
    ],
    "traffic": [
        "kẹt xe cứng ở cầu, tới {poi} trễ chắc",
        "đường đông quá, đổi phương tiện nhé",
        "kẹt xe {time}, lịch có kịp không",
        "tắc đường dài, bỏ bớt 1 điểm nhé",
        "giờ cao điểm kẹt quá, đi đường khác",
    ],
    "budget": [
        "chi quá {amount} rồi, chiều đi chỗ rẻ thôi",
        "vượt ngân sách, cắt điểm tốn vé nhé",
        "hết tiền rồi, chỉ đi chỗ miễn phí",
        "ngân sách còn ít, gợi ý chỗ rẻ gần {poi}",
        "vé {poi} đắt quá, đổi chỗ khác",
    ],
    "lost": [
        "lạc đường rồi, đang ở đâu không rõ",
        "đi lạc khỏi đoàn, chỉ đường về {poi}",
        "bị lạc, gửi lại vị trí {poi} giúp",
        "lạc nhau ở chợ, tập trung ở đâu",
        "đi nhầm đường tới {poi}, quay lại sao",
    ],
}

# word -> swappable synonyms (rule-based paraphrase, pre-LLM phase)
SYNONYMS: dict[str, list[str]] = {
    "mưa": ["mưa", "mưa to", "mưa lớn", "mưa rào"],
    "mệt": ["mệt", "đuối", "oải", "hết sức"],
    "bỏ": ["bỏ", "hủy", "skip", "cắt"],
    "kẹt xe": ["kẹt xe", "tắc đường", "đường đông"],
    "đóng cửa": ["đóng cửa", "ngưng đón khách", "nghỉ"],
    "trễ": ["trễ", "muộn", "delay"],
    "thêm": ["thêm", "cho thêm", "muốn ghé thêm"],
    "đổi": ["đổi", "dời", "chuyển"],
    "quá": ["quá", "vượt", "lố"],
}
