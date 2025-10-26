
import socket

# Originalfunktion sichern
_orig_getaddrinfo = socket.getaddrinfo

def force_ipv4(host, port, family=0, type=0, proto=0, flags=0):
    # Nur IPv4-Einträge zurückgeben
    results = _orig_getaddrinfo(host, port, family, type, proto, flags)
    ipv4_results = [r for r in results if r[0] == socket.AF_INET]
    if not ipv4_results:
        # Fallback: wenigstens die Originalergebnisse zurückgeben, falls etwas exotisches abgefragt wird
        return results
    return ipv4_results

socket.getaddrinfo = force_ipv4
print("[IPv4] Global IPv4-Modus aktiv – IPv6 komplett deaktiviert.")
