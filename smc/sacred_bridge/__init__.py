"""All access to the read-only sacred repo lives behind this package.

Nothing outside sacred_bridge may touch the sacred paths. Reads are tolerant:
missing or partially-written files yield typed "unavailable" results, never
exceptions crossing into UI code.
"""
