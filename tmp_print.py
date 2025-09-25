from pathlib import Path
import re
text = Path('server/database/sqlite_temp_client.py').read_text()
match = re.search(r"    async def create_user.*?        except Exception as e:\n            logger.error\(f\"Error creating user: {e}\"\)\n            raise\n", text, re.S)
print(bool(match))
if match:
    print('---')
    print(match.group(0))
