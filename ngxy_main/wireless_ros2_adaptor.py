import enum

TOPIC_WIRELESS_OUT = "/wireless/wireless_result"  # WithType WirelessJson
FACTION_QUERY_SRV = "/radar_service/get_current_faction"  # WithType GetCurrentFaction
GAME_STATUS_IN = "/referee/game_status"  # WithType GameStatus
DEFAULT_QOS = 10


class Faction(enum.Enum):
    RED = "red"
    BLUE = "blue"
    UNKNOWN = "unknown"


#  ===

import threading

import rclpy
from rclpy.node import Node

try:
    from radar_msg.msg import WirelessJson  # type: ignore
    from radar_msg.srv import FactionQuery, FactionQuery_Request, FactionQuery_Response  # type: ignore
    from radar_msg.msg import GameStatus  # type: ignore
except ImportError as e:
    import sys

    raise ImportError(
        f"Check if u've already `source /path/to/setup.bash`. "
        f"Searching pathes are: \n{sys.path}."
    ) from e


class WirelessRos2AdaptorNode(Node):
    def __init__(
        self,
        on_encrypt_level_change_callback=lambda new_level: None,
        node_name: str = "wireless_ros2_adaptor_node",
        namespace: str | None = None,
    ):
        if namespace is None:
            super().__init__(node_name)
        else:
            super().__init__(node_name, namespace=namespace)
        self.pubber_ = self.create_publisher(
            WirelessJson,
            TOPIC_WIRELESS_OUT,
            DEFAULT_QOS,
        )
        self.faction_cln_ = self.create_client(FactionQuery, FACTION_QUERY_SRV)
        self.subber_ = self.create_subscription(
            GameStatus,
            GAME_STATUS_IN,
            self.on_recv_game_status,
            DEFAULT_QOS,
        )

        self.on_encrypt_level_change = on_encrypt_level_change_callback
        self.lastest_encrypt_level_ = -1

    def get_faction(self) -> Faction:
        while not self.faction_cln_.wait_for_service(timeout_sec=1.0):
            self.get_logger().info("Waiting for FactionQuery service...")

        faction_req = FactionQuery_Request()
        future = self.faction_cln_.call_async(faction_req)
        rclpy.spin_until_future_complete(self, future)

        faction_response: FactionQuery_Response = future.result()
        if faction_response is None:
            self.get_logger().warning("Failed to get current faction from service.")
            return Faction.UNKNOWN

        faction_str = faction_response.faction
        if faction_str.upper() == "RED":
            return Faction.RED
        elif faction_str.upper() == "BLUE":
            return Faction.BLUE
        else:
            self.get_logger().warning(f"Received unknown faction string: {faction_str}")
            return Faction.UNKNOWN

    def publish_wireless_result(self, json_str: str):
        msg = WirelessJson()
        msg.jsondata = json_str
        self.pubber_.publish(msg)
        self.get_logger().info(f"Published wireless result: {json_str}")

    def on_recv_game_status(self, msg: GameStatus):
        if msg.current_encrypt_level != self.lastest_encrypt_level_:
            self.get_logger().info(
                f"Game status updated: current_encrypt_level changed from "
                f"{self.lastest_encrypt_level_} to {msg.current_encrypt_level}"
            )
            # Call trigger
            self.on_encrypt_level_change(msg.current_encrypt_level)
        self.lastest_encrypt_level_ = msg.current_encrypt_level


class WirelessRos2AdaptorNodeThreaded(WirelessRos2AdaptorNode):
    """
    Usage (With ROS2 environment properly sourced):

    ### Lifecycle
    ```
    node = WirelessRos2AdaptorNodeThreaded(on_encrypt_level_change_callback=my_callback)
    node.start()
    ... # do something
    node.stop()
    ```

    ### Publishing wireless result
    ```
    node.publish_wireless_result(json_str)
    ```

    ### Query current faction
    ```
    faction: Faction = node.get_faction()
    ```

    ### Callback
    the `on_encrypt_level_change_callback` will be called with the new encrypt level as
    the only argument whenever the encrypt level changes (no matter bigger or smaller).

    Recommanded signature:
    `def my_callback(new_level: int) -> None: ...`

    A try-except-finally block is recommended to ensure the node is stopped properly.

    """

    def __init__(
        self,
        on_encrypt_level_change_callback=lambda new_level: None,
        node_name: str = "wireless_ros2_adaptor_node",
        namespace: str | None = None,
    ):
        super().__init__(
            on_encrypt_level_change_callback,
            node_name=node_name,
            namespace=namespace,
        )
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
