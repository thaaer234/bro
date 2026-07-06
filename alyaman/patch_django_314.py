import sys
from copy import copy

# Monkeypatch Django template Context for Python 3.14 compatibility
try:
    from django.template import context
    
    if hasattr(context, 'BaseContext'):
        def base_context_copy(self):
            # Create a new instance of the exact class (e.g. BaseContext, Context, RequestContext)
            duplicate = self.__class__.__new__(self.__class__)
            # Copy all instance dictionary attributes
            duplicate.__dict__.update(self.__dict__)
            # Make a shallow copy of the dicts list
            duplicate.dicts = self.dicts[:]
            return duplicate
            
        context.BaseContext.__copy__ = base_context_copy
        print("Successfully monkeypatched Django BaseContext.__copy__ for Python 3.14 compatibility.")
        
except Exception as e:
    import traceback
    print(f"Warning: Failed to apply Python 3.14 Django Context patch: {e}")
    traceback.print_exc()
