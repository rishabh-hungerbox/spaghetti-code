from django.core.cache import cache
import json


class CacheHandler:
    def set_dict_cache_data(key, data, timeout=24*60*60):
        """
        Store dictionary data in cache
        Args:
            key: Cache key
            data: Dictionary data to store
            timeout: Time in seconds for cache to expire (optional)
        """
        try:
            cache.set(key, json.dumps(data), timeout)
            return True
        except Exception as e:
            print(f"Error setting cache: {str(e)}")
            return False


    def get_dict_cache_data(key):
        """
        Retrieve dictionary data from cache
        Args:
            key: Cache key
        Returns:
            Dictionary data if found, None if not found
        """
        try:
            data = cache.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            print(f"Error getting cache: {str(e)}")
            return None
