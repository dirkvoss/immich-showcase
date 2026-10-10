"""Bonjour-Dienst: waehlt nur echte LAN-Adressen und baut den Diensteintrag."""
import types

import bonjour


def adapter(name, *ips):
    return types.SimpleNamespace(name=name, nice_name=name, ips=[types.SimpleNamespace(ip=i, is_IPv4=":" not in i) for i in ips])


def test_nur_echte_lan_adressen():
    karten = [adapter("lo", "127.0.0.1"), adapter("docker0", "172.17.0.1"), adapter("br-1a2b3c", "172.18.0.1"), adapter("veth12", "172.19.0.1"),
              adapter("eth0", "192.168.1.20", "fe80::1"), adapter("wlan0", "10.0.5.7"), adapter("wg0", "10.99.0.2"), adapter("eth1", "203.0.113.5"),
              adapter("eth2", "169.254.7.7"), adapter("eth3", "192.168.1.20")]
    assert bonjour.lan_adressen(karten) == ["192.168.1.20", "10.0.5.7"]               # ohne Doppelte, ohne Docker/VPN/oeffentliche/Link-Local


def test_sauberer_name():
    assert bonjour.sauberer_name("Frameside (Entwicklung)") == "Frameside (Entwicklung)"
    assert bonjour.sauberer_name("a.b\nc") == "a b c"
    assert bonjour.sauberer_name("") == "Frameside"
    assert len(bonjour.sauberer_name("x" * 200)) == 60


def test_dienst_info():
    i = bonjour.dienst_info("Meine Fotos", 8090, ["192.168.1.20", "10.0.5.7"], "2.17.0", "immich")
    assert i.type == "_showcase._tcp.local." and i.name == "Meine Fotos._showcase._tcp.local."
    assert i.port == 8090 and sorted(i.parsed_addresses()) == ["10.0.5.7", "192.168.1.20"]
    assert i.decoded_properties == {"v": "2.17.0", "auth": "immich", "name": "Meine Fotos"}


def test_fester_name_im_netz(monkeypatch):
    monkeypatch.delenv("SHOWCASE_MDNS_NAME", raising=False)
    assert bonjour.rechnername() == "showcase"
    assert bonjour.dienst_info("X", 8090, ["192.168.2.5"]).server == "showcase.local."
    monkeypatch.setenv("SHOWCASE_MDNS_NAME", "bilder.heim")
    assert bonjour.rechnername() == "bilder"
    monkeypatch.setenv("SHOWCASE_MDNS_NAME", "!!!")
    assert bonjour.rechnername() == "showcase"                        # nur ungueltige Zeichen: Vorgabe
