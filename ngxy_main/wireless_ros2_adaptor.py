TOPIC_WIRELESS_OUT = "/wireless_node/wireless_result"

import threading

import rclpy
from rclpy.node import Node

try:
    from radar_msg.msg import WirelessJson  # type: ignore
except ImportError as e:
    import sys

    raise ImportError(
        f"Check if u've already `source /path/to/setup.bash`. "
        f"Searching pathes are: \n{sys.path}."
    ) from e


class WirelessRos2AdaptorNode(Node):
    def __init__(self):
        super().__init__("wireless_ros2_adaptor_node")
        self.pubber_ = self.create_publisher(
            WirelessJson,
            TOPIC_WIRELESS_OUT,
            10,
        )

    def publish_wireless_result(self, json_str: str):
        msg = WirelessJson()
        msg.jsondata = json_str
        self.pubber_.publish(msg)
        self.get_logger().info(f"Published wireless result: {json_str}")


class WirelessRos2AdaptorNodeThreaded(WirelessRos2AdaptorNode):
    """
    Usage (With ROS2 environment properly sourced):

    ```
    node = WirelessRos2AdaptorNodeThreaded()
    node.start()
    ...
    # when a frame was decoded and you have the json string ready to publish, just call:
    node.publish_wireless_result(json_string)
    ...
    node.stop()
    ```

    A try-except-finally block is recommended to ensure the node is stopped properly.

    """

    def __init__(self):
        super().__init__()
        self._lock = threading.Lock()
        self._thread = None

    def publish_wireless_result(self, json_str: str):
        """
        Note that if two frames in a json_str,
        the second one will be ignored at receiver side!
        """
        with self._lock:
            super().publish_wireless_result(json_str)

    def start(self):
        if not rclpy.ok():
            rclpy.init()

        self._thread = threading.Thread(target=rclpy.spin, args=(self,), daemon=True)
        self._thread.start()

    def stop(self):
        if self._thread is None:
            return

        self.destroy_node()
        self._thread.join(timeout=1)

        if self._thread.is_alive() and rclpy.ok():
            rclpy.shutdown()
            self._thread.join(timeout=1)

        if not self.is_running:
            self.get_logger().info(
                "WirelessRos2AdaptorNodeThreaded stopped successfully."
            )
        else:
            self.get_logger().warning(
                "Failed to stop WirelessRos2AdaptorNodeThreaded properly."
            )

    @property
    def is_running(self):
        return self._thread is not None and self._thread.is_alive()


def main(args=None):
    rclpy.init(args=args)
    node = WirelessRos2AdaptorNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
