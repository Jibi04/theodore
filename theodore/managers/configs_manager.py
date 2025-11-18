from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from theodore.models.configs import Configs
from theodore.models.base import engine
from theodore.core.utils import user_error, base_logger, error_logger, send_message, JSON_DIR
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
            user_error(e)
            return send_message(False, message=f'{type(e).__name__}: {e}')


    async def set(self, category, default_location=None, api_key=None, default_path=None, target_dirs=None, file_patterns=None, **kwargs):
        data_map = {"category": category}

        if default_location: data_map['default_location'] = default_location
        if api_key: data_map['api_key'] = api_key
        if default_path: data_map['default_path'] = default_path
        if target_dirs: data_map[target_dirs] = target_dirs
        if file_patterns: data_map['file_patterns'] = file_patterns

        try:
            async with engine.begin() as conn:
                base_logger.internal('Preparing configs statement')
                stmt = update(Configs).values(**data_map)

                base_logger.internal('Executing configs statement')
                await conn.execute(stmt)
                base_logger.debug('config settings updated')

                send_message(True, message='config settings updated')
        except SQLAlchemyError as e:
            base_logger.internal(f'Database error Aborting ...')
            user_error(e)
            return send_message(False, message='DataBase Error')
        except Exception as e:
            base_logger.internal(f'Database error Aborting ...')
            user_error(e)
            return send_message(False, message='An unknown Error occurred')
        

    async def show_configs(self, weather: bool = False, downloads: bool = False, todos: bool = False):

        if weather: stmt = stmt.where(Configs.c.category == 'weather')
        if downloads: stmt = stmt.where(Configs.c.category == 'downloads')
        if todos: stmt = stmt.where(Configs.c.category == 'todos')

        try:
            base_logger.internal('Starting connection with Database')
            async with engine.begin() as conn:
                base_logger.internal('Preparing select statement')
                stmt = select(Configs)

                base_logger.internal('Executing select statement')
                result = await conn.execute(stmt)

                base_logger.internal('Converting row objects to dictionaries')
                configs = [dict(row) for row in result.fetchall()]
                base_logger.debug(f'Configs dictionaries created {configs}')
                return send_message(True, data=configs)
        except SQLAlchemyError as e:
            base_logger.internal(f'Database error Aborting ...')
            user_error(e)
            return send_message(False, message='DataBase Error')
        except Exception as e:
            base_logger.internal(f'Database error Aborting ...')
            user_error(e)
            return send_message(False, message='An unknown Error occurred')


    async def load_db_configs(self, category: str = None):
        try:
            async with engine.begin() as conn:
                base_logger.internal('preparing config load statement')
                stmt = select(Configs)

                base_logger.internal('filtering configs ...')
                if category:
                    stmt = stmt.where(Configs.c.category == category)

                base_logger.internal('Executing config load statement')
                result = await conn.execute(stmt)
                configs_map = result.mappings.all()

                base_logger.debug(f'Executed configs {configs_map}')

                if not configs_map:
                    msg = 'Aborting... no matching record found'
                    base_logger.internal(msg)
                    return send_message(False, message=msg + 'use configs set to set new config row')
                
                return send_message(True, data=configs_map)
        except SQLAlchemyError as e:
            base_logger.internal(f'Database error Aborting ...')
            user_error(e)
            return send_message(False, message='DataBase Error')
        except Exception as e:
            base_logger.internal(f'Database error Aborting ...')
            user_error(e)
            return send_message(False, message='An unknown Error occurred')


    async def save_db_configs(self, configs, category: str = None):
        try:

            async with engine.begin() as conn:
                base_logger.internal('preparing save config statement')
                stmt = update(Configs)

                base_logger.internal('Applying filters to statement')
                if category:
                    stmt = stmt.where(Configs.c.category == category)
                
                stmt = stmt.values(**configs)

                base_logger.internal('Preparing to execute')
                result = await conn.execute(stmt)
                base_logger.internal(f'{result.rowcount} updates done: {configs}')

                if result.rowcount == 0:
                    base_logger.internal('Aborting ....')
                    base_logger.internal('Unable to update config data')
                    return send_message(False, message='Unable to update configs data')
                
                return send_message(True, message='Configs data saved')

        except SQLAlchemyError as e:
            base_logger.internal(f'Database error Aborting ...')
            user_error(e)
            return send_message(False, message='DataBase Error')
        except Exception as e:
            base_logger.internal(f'Database error Aborting ...')
            user_error(e)
            return send_message(False, message='An unknown Error occurred')