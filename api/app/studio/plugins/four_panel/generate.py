"""Re-export builder for skill script / local imports."""
from app.studio.four_panel_comic import build_comic_from_fields, write_comic_outputs, main

__all__ = ["build_comic_from_fields", "write_comic_outputs", "main"]

if __name__ == "__main__":
    main()
