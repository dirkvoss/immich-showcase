"""Sonnenauf- und -untergang (NOAA-Naeherung, auf wenige Minuten genau) - fuer die Nachtruhe nach Sonnenstand."""
import datetime
import math


def sonnenzeiten(lat, lon, tag):
    """(Aufgang, Untergang) als lokale Zeit des Servers (naive datetime) am Tag `tag`; None bei Polartag/Polarnacht."""
    n = tag.timetuple().tm_yday
    g = 2 * math.pi / 365 * (n - 1)
    zeitgl = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g) - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    dekl = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g) - 0.006758 * math.cos(2 * g)
            + 0.000907 * math.sin(2 * g) - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
    b = math.radians(lat)
    cos_ha = math.cos(math.radians(90.833)) / (math.cos(b) * math.cos(dekl)) - math.tan(b) * math.tan(dekl)
    if abs(cos_ha) > 1:
        return None
    ha = math.degrees(math.acos(cos_ha))
    mitternacht = datetime.datetime(tag.year, tag.month, tag.day, tzinfo=datetime.timezone.utc)

    def lokal(minuten):
        return (mitternacht + datetime.timedelta(minutes=minuten)).astimezone().replace(tzinfo=None, second=0, microsecond=0)
    return lokal(720 - 4 * (lon + ha) - zeitgl), lokal(720 - 4 * (lon - ha) - zeitgl)
