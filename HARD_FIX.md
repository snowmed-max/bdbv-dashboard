# Hard fix

This version replaces the dashboard JavaScript with a clean robust initializer:
- render fallback data immediately;
- load data/*.json asynchronously;
- show visible runtime error messages;
- avoid any direct browser call to GDELT.
