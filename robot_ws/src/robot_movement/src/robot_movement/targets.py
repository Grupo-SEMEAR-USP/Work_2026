import math


def parse_tag_id(payload):
    tag_id = int(payload)
    if not 0 <= tag_id <= 2**31 - 1:
        raise ValueError("ID da AprilTag fora da faixa")
    return tag_id


def block_position(msg, tag_id):
    for detection in msg.detections:
        if list(detection.id) != [tag_id]:
            continue
        pos = detection.pose.pose.pose.position
        if all(math.isfinite(v) for v in (pos.x, pos.y, pos.z)) and pos.z > 0:
            return pos.x, pos.z
    return None


def container_position(msg, color):
    candidates = [det for det in msg.detections
                  if det.color == color and 0 <= det.center_x < msg.image_width
                  and 0 <= det.center_y < msg.image_height
                  and math.isfinite(det.area_px) and det.area_px > 0]
    if not candidates:
        return None
    nearest = max(candidates, key=lambda det: det.area_px)
    return nearest.center_x / msg.image_width, nearest.center_y / msg.image_height
