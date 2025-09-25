from pathlib import Path
import textwrap

path = Path('server/database/sqlite_temp_client.py')
text = path.read_text()
old = textwrap.dedent('''
    async def create_user(self, user_id: str, email: str, user_type: UserType = UserType.FREE, 
                         name: Optional[str] = None) -> Dict[str, Any]:
        """Create a new user"""
        try:
            # Set initial credits based on user type
            initial_credits = 5.0 if user_type == UserType.FREE else 0.0
            
            query = """
                INSERT INTO users (user_id, email, name, user_type, credits)
                VALUES (?, ?, ?, ?, ?)
            """
            success = await self._execute_update(query, (user_id, email, name, user_type.value, initial_credits))
            
            if success:
                user = await self.get_user(user_id)
                # Add 'id' field to match expected format
                if user:
                    user['id'] = user['user_id']
                return user
            else:
                raise Exception("Failed to create user")
                
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            raise
''')

new = textwrap.dedent('''
    async def create_user(self, user_id: str, email: str, user_type: UserType = UserType.FREE, 
                         name: Optional[str] = None) -> Dict[str, Any]:
        """Create a new user"""
        try:
            # Return existing record when the email has already been provisioned
            existing_user = await self._execute_single(
                "SELECT * FROM users WHERE email = ?",
                (email,)
            )
            if existing_user:
                existing_user['id'] = existing_user['user_id']
                return existing_user

            # Set initial credits based on user type
            initial_credits = 5.0 if user_type == UserType.FREE else 0.0
            
            query = """
                INSERT INTO users (user_id, email, name, user_type, credits)
                VALUES (?, ?, ?, ?, ?)
            """
            success = await self._execute_update(query, (user_id, email, name, user_type.value, initial_credits))
            
            if success:
                user = await self.get_user(user_id)
                # Add 'id' field to match expected format
                if user:
                    user['id'] = user['user_id']
                return user
            raise Exception("Failed to create user")
                
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            raise
''')

if old not in text:
    raise SystemExit('original block not found')
path.write_text(text.replace(old, new))
