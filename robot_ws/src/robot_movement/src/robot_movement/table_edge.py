import math

import rospy


DIRECTION_SIGN = {"esquerda": 1.0, "direita": -1.0}


class TableEdge:
    def __init__(self):
        self.return_max = rospy.get_param("~table_return_max_cm", 30.0)
        self.delta = rospy.get_param("~edge_delta_cm", 12.0)
        self.samples = rospy.get_param("~edge_samples", 2)
        if self.delta <= 0 or self.return_max <= 0 or self.samples < 1:
            raise ValueError("Configuração de borda inválida")
        self.reset()

    def reset(self):
        self.sample = None
        self.count = 0

    def on_range(self, msg, direction):
        left, right = msg.us_front_left, msg.us_front_right
        outer, inner = (left, right) if direction == "esquerda" else (right, left)
        near = any(math.isfinite(v) and 0.0 < v <= self.return_max for v in (outer, inner))
        valid_inner = math.isfinite(inner) and 0.0 < inner <= self.return_max
        edge = valid_inner and (math.isnan(outer) or
                                (math.isfinite(outer) and outer - inner >= self.delta))
        self.count = self.count + 1 if edge else 0
        self.sample = rospy.Time.now(), near, self.count >= self.samples

    def state(self, since, max_age=0.30):
        if self.sample is None:
            return False, False
        stamp, near, edge = self.sample
        if stamp < since or not 0 <= (rospy.Time.now() - stamp).to_sec() <= max_age:
            return False, False
        return near, edge
