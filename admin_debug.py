# alyaman/middleware.py
class RecursionProtectionMiddleware:
    """
    Middleware لمنع مشاكل الاستدعاء الذاتي والـ recursion في templates
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.processing_paths = set()
    
    def __call__(self, request):
        path = request.path
        
        # منع معالجة نفس المسار بشكل متكرر
        if path in self.processing_paths:
            return self.get_response(request)
        
        self.processing_paths.add(path)
        try:
            response = self.get_response(request)
        finally:
            self.processing_paths.remove(path)
        
        return response
    
    @staticmethod
    def safe_render(template, context=None):
        """طريقة آمنة لعرض templates لمنع recursion"""
        from django.template import TemplateDoesNotExist
        
        if context is None:
            context = {}
        
        # إضافة حماية ضد recursion في context processors
        if '_recursion_guard' in context:
            return ''
        
        context['_recursion_guard'] = True
        
        try:
            return template.render(context)
        except RecursionError:
            return "<div>Recursion error prevented</div>"
        except Exception as e:
            return f"<div>Template error: {str(e)}</div>"
        finally:
            if '_recursion_guard' in context:
                del context['_recursion_guard']