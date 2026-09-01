"""Portable interface monitor using psutil. Windows advanced attribution is separate."""

from __future__ import annotations

from netwatch.core.models import ConnectionSnapshot, InterfaceSnapshot
from netwatch.monitors.network.base import NetworkMonitor


class PsutilNetworkMonitor(NetworkMonitor):
    def interfaces(self) -> list[InterfaceSnapshot]:
        import psutil

        counters = psutil.net_io_counters(pernic=True)
        stats = psutil.net_if_stats()
        addresses = psutil.net_if_addrs()
        result: list[InterfaceSnapshot] = []
        for name, counter in counters.items():
            values = addresses.get(name, [])
            family_name = lambda item: getattr(getattr(item, "family", None), "name", "")
            mac = next((item.address for item in values if family_name(item) in {"AF_LINK", "AF_PACKET"}), None)
            ips = tuple(item.address for item in values if family_name(item) in {"AF_INET", "AF_INET6"})
            result.append(InterfaceSnapshot(name, bool(stats.get(name) and stats[name].isup), ips, mac, counter.bytes_recv, counter.bytes_sent))
        return result

    def connections(self) -> list[ConnectionSnapshot]:
        import psutil

        items: list[ConnectionSnapshot] = []
        for connection in psutil.net_connections(kind="inet"):
            if not connection.raddr:
                continue
            process_name = None
            if connection.pid is not None:
                try:
                    process_name = psutil.Process(connection.pid).name()
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    process_name = None
            local = connection.laddr
            remote = connection.raddr
            items.append(ConnectionSnapshot(
                connection.pid, process_name, "TCP" if connection.type == 1 else "UDP",
                getattr(local, "ip", None), getattr(local, "port", None),
                getattr(remote, "ip", None), getattr(remote, "port", None), connection.status or None,
            ))
        return items
