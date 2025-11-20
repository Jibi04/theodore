from sqlalchemy import select, update, insert
from sqlalchemy.exc import SQLAlchemyError
from theodore.models.configs import Configs
from theodore.models.base import engine
from theodore.core.utils import user_error, base_logger, error_logger, send_message, JSON_DIR, user_success
from pathlib import Path
import json



CONFIG_FILE = JSON_DIR / "configs.json"
MOVIE_FILE = JSON_DIR / "movies.json"


class Configs_manager:

    def load_file(self, movie=False, config=False):
        if movie: file = MOVIE_FILE
        if config: file = CONFIG_FILE

        if not movie and not config:
            raise NotImplementedError('File not saved no path set.')

        if MOVIE_FILE.exists():
            try:
                configs = json.loads(file.read_text())
                base_logger.debug(f'Loaded Configs: {configs}')
                return configs
            except json.JSONDecodeError:
                return {}
        return {}

    
    def save_file(self, data: dict, config=False, movie=False):
        if config: file = CONFIG_FILE
        if movie: file = MOVIE_FILE

        if not movie and not config:
            raise NotImplementedError('File not saved no path set.')

        try:
            file.write_text(json.dumps(data, indent=4))
            base_logger.internal('Successfully saved config file')
        except Exception as e:
            error_logger.internal('An unknown error occurred Aborting ...')
            user_error(str(e))
            return send_message(False, message=f'{type(str(e)).__name__}: {e}')


    async def new_category(self, category, default_location=None, api_key=None, default_path=None):
        data_map = {
            "category": category
            }

        if default_location: data_map['default_location'] = default_location
        if api_key: data_map['api_key'] = api_key
        if default_path: data_map['default_path'] = default_path

        try:
            async with engine.begin() as conn:
                base_logger.internal('Preparing configs statement')
                stmt = insert(Configs).values(**data_map)

                base_logger.internal('Executing configs statement')
                response = await conn.execute(stmt.returning(Configs.c.category, Configs.c.default_location, Configs.c.default_path))
                base_logger.debug('config settings updated')

                return send_message(True, message='config settings updated', data=response.mappings().all())
        except SQLAlchemyError as e:
            user_error(str(e))
            return send_message(False, message='DataBase Error')
        except Exception as e:
            user_error(str(e))
            return send_message(False, message='An unknown Error occurred')
        

    async def show_configs(self, weather: bool = False, downloads: bool = False, todos: bool = False):
        try:
            base_logger.internal('Starting connection with Database')
            async with engine.begin() as conn:
                base_logger.internal('Preparing select statement')
                stmt = select(Configs)

                if weather: stmt = stmt.where(Configs.c.category == 'weather')
                if downloads: stmt = stmt.where(Configs.c.category == 'downloads')
                if todos: stmt = stmt.where(Configs.c.category == 'todos')

                base_logger.internal('Executing select statement')
                result = await conn.execute(stmt)
                configs_data = result.mappings()

                base_logger.debug(f'Configs dictionaries created {configs_data}')
                return send_message(True, data=configs_data)
        except SQLAlchemyError as e:
            base_logger.internal(f'Database error Aborting ...')
            user_error(str(e))
            return send_message(False, message='DataBase Error')
        except Exception as e:
            base_logger.internal(f'Database error Aborting ...')
            user_error(str(e))
            return send_message(False, message='An unknown Error occurred')


    async def load_db_configs(self, category: str = None):
        try:
            async with engine.begin() as conn:
                base_logger.internal('preparing config load statement')
                stmt = select(Configs)
                if category:
                    stmt = stmt.where(Configs.c.category == category)

                base_logger.internal('Executing config load statement')
                result = await conn.execute(stmt)
                configs_map = result.mappings().all()
                if not configs_map:
                    msg = 'Aborting... no matching record found'
                    return send_message(False, message=msg + ' use configs set to set new config row')
                base_logger.debug(f'Executed configs {configs_map}')
                return send_message(True, data=configs_map)
        except SQLAlchemyError as e:
            base_logger.internal(f'Database error Aborting ...')
            user_error(str(e))
            return send_message(False, message='DataBase Error')
        except Exception as e:
            base_logger.internal(f'Database error Aborting ...')
            user_error(str(e))
            return send_message(False, message='An unknown Error occurred')
        return


    async def update_db_configs(self, category, default_location=None, api_key=None, default_path=None):
        try:
            data_map = {
            "category": category
            }

            if default_location: data_map['default_location'] = default_location
            if api_key: data_map['api_key'] = api_key
            if default_path: data_map['default_path'] = default_path

            async with engine.begin() as conn:
                base_logger.internal('preparing save config statement')
                stmt = update(Configs).where(Configs.c.category == category)
                stmt = stmt.values(**data_map)

                base_logger.internal('Preparing to execute')
                result = await conn.execute(stmt.returning(Configs.c.category, Configs.c.default_location, Configs.c.default_path))
                updated_configs = result.mappings().all() # print('got here')   
                base_logger.internal(f'{result.rowcount} updates done: {updated_configs}')
                if result.rowcount == 0:
                    base_logger.debug(f'Unable to update config data row_count -> {result.rowcount}')
                    return send_message(False, message='Unable to update configs data')
                
                return send_message(True, message='Configs data saved', data=updated_configs)
        except SQLAlchemyError as e:
            user_error(str(e))
            return send_message(False, message='DataBase Error')
        except Exception as e:
            base_logger.internal(f'Database error Aborting ...')
            user_error(str(e))
            return send_message(False, message='An unknown Error occurred')
        return