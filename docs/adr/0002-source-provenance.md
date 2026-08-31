# Render cached source without claiming execution fidelity

The renderer reads the existing `linecache` entry and never refreshes it. A running code object cannot generally recover the exact source that executed after files change, so unavailable or potentially stale source is shown honestly instead of silently reading newer disk content.
