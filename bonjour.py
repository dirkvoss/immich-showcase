#!/usr/bin/env python3
"""Meldet Frameside per Bonjour/mDNS im Netz an (Diensttyp _showcase._tcp), damit die iPhone-App den Server im WLAN selbst findet.

Laeuft als eigener kleiner Container mit Host-Netzwerk (docker-compose.bonjour.yml), weil Bonjour-Meldungen (Multicast) aus dem normalen
Docker-Netz nicht ins Heimnetz kommen. Nur auf Linux-Docker sinnvoll; zwischen VLANs braucht der Router einen mDNS-Weiterleiter.
Umgebung: SHOWCASE_PORT (8090), RAHMEN_WEB_NAME, RAHMEN_WEB_AUTH, SHOWCASE_VERSION, SHOWCASE_MDNS_NAME (Vorgabe "showcase" -> http://showcase.local).
"""
import ipaddress
import os
import re
import signal
import socket
import sys
import threading

TYP = "_showcase._tcp.local."
PRIVAT = [ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")]            # nur echte Heimnetz-Adressen (RFC 1918)
# Netzwerkkarten, die nicht ins Heimnetz fuehren: Loopback, Docker, virtuelle Karten, VPN/Tunnel
UNERWUENSCHT = ("lo", "docker", "br-", "veth", "virbr", "tun", "tap", "wg", "zt", "tailscale", "utun", "awdl", "llw", "cni", "flannel", "cali")


def lan_adressen(adapter_liste=None):
    """IPv4-Adressen der echten Netzwerkkarten (privat, kein Loopback, kein Docker/VPN)."""
    if adapter_liste is None:
        import ifaddr
        adapter_liste = ifaddr.get_adapters()
    erg = []
    for a in adapter_liste:
        name = (getattr(a, "name", "") or getattr(a, "nice_name", "") or "").lower()
        if name.startswith(UNERWUENSCHT):
            continue
        for i in a.ips:
            if not i.is_IPv4:
                continue
            try:
                ip = ipaddress.ip_address(i.ip)
            except ValueError:
                continue
            if any(ip in n for n in PRIVAT) and str(ip) not in erg:
                erg.append(str(ip))
    return erg


def sauberer_name(name):
    """Dienstname fuer Bonjour: ohne Steuerzeichen und Punkte, hoechstens 60 Zeichen."""
    n = re.sub(r"[\x00-\x1f.]", " ", str(name or "")).strip()[:60].strip()
    return n or "Frameside"


def rechnername():
    """Name im Netz (<name>.local): vorgegeben 'showcase' - dann geht im ganzen Heimnetz die kurze Adresse http://showcase.local:8090. Ueberschreiben mit SHOWCASE_MDNS_NAME."""
    n = re.sub(r"[^A-Za-z0-9-]", "-", os.environ.get("SHOWCASE_MDNS_NAME", "showcase").split(".")[0]).strip("-")[:40]
    return n or "showcase"


def dienst_info(name, port, adressen, version="", auth="pin", server=None):
    from zeroconf import ServiceInfo
    n = sauberer_name(name)
    return ServiceInfo(TYP, f"{n}.{TYP}", addresses=[socket.inet_aton(a) for a in adressen], port=int(port),
                       properties={"v": str(version)[:20], "auth": str(auth)[:10], "name": n}, server=server or f"{rechnername()}.local.")


def main():
    from zeroconf import Zeroconf
    port = int(os.environ.get("SHOWCASE_PORT", "8090") or 8090)
    name, version, auth = os.environ.get("RAHMEN_WEB_NAME", "Frameside"), os.environ.get("SHOWCASE_VERSION", ""), os.environ.get("RAHMEN_WEB_AUTH", "pin")
    adressen = lan_adressen()
    if not adressen:
        print("Keine Netzwerkadresse im Heimnetz gefunden - Bonjour-Dienst beendet.", file=sys.stderr)
        sys.exit(1)
    zc = Zeroconf()
    info = dienst_info(name, port, adressen, version, auth)
    zc.register_service(info)
    print(f"Bonjour: {sauberer_name(name)} auf {', '.join(adressen)}:{port} angemeldet ({TYP})", flush=True)
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    while not stop.wait(300):                                   # alle 5 Minuten: haben sich die Adressen geaendert (DHCP)?
        neu = lan_adressen()
        if neu and neu != adressen:
            adressen = neu
            zc.update_service(dienst_info(name, port, adressen, version, auth))
            print("Bonjour: Adressen aktualisiert:", ", ".join(adressen), flush=True)
    zc.unregister_all_services()
    zc.close()


if __name__ == "__main__":
    main()
