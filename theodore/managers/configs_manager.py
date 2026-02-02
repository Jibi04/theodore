
from theodore.models.configs import ConfigTable
from theodore.core.utils import get_configs_table
from theodore.core.informers import user_error, send_message
from theodore.core.db_operations import DBTasks


class ConfigManager:
    async def upsert_category(self, data: dict) -> dict:
        try:
            with DBTasks(ConfigTable) as configs_manager:
                category = data.get('category')
                await configs_manager.upsert_features(data, primary_key={'category': category})
                return send_message(True, message='done')
        except Exception as e:
            raise
    
    async def show_configs(self, args_map) -> dict:
        from sqlalchemy.exc import SQLAlchemyError
        try:
            with DBTasks(ConfigTable) as configs_manager:
                for category, validation in args_map.items():
                    if validation:
                        if category == 'all':
                            response = await configs_manager.get_features()
                            return send_message(True, data=get_configs_table(response))
                        else:
                            response = await configs_manager.get_features(and_conditions={'category': category})
                            return send_message(True, data=get_configs_table(response))
                if not response:
                    return send_message(False, message='No configs have been added yet!')
        except SQLAlchemyError as e:
            user_error(str(e))
            return send_message(False, message='DataBase Error')
        except Exception as e:
            user_error(str(e))
            return send_message(False, message='An unknown Error occurred')
