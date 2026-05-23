# -*- coding: utf-8 -*-
class Device:
    class ScanInfo:
        def __init__(self) -> None:
            self.reset()

        def reset(self) -> None:
            self.tick: float = 0.

    def __init__(self) -> None:
        self.scan = Device.ScanInfo()
