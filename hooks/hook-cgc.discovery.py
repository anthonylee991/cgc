"""PyInstaller hook for cgc.discovery package.

The discovery package uses __getattr__ lazy imports for heavy modules
(GliNER, GliREL, unified, router). PyInstaller can't detect these
automatically, so we declare them as hidden imports here.
"""

from PyInstaller.utils.hooks import collect_submodules

# Collect all cgc submodules so nothing is missed
hiddenimports = collect_submodules('cgc')
