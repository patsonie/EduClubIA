from rest_framework.pagination import PageNumberPagination


class PaginationOptionnelle(PageNumberPagination):
    """
    Pagination à la demande : sans paramètre `page` ni `page_size`, la liste
    complète est renvoyée (compatibilité avec le front actuel) ; avec l'un
    des deux, la réponse est paginée ({count, next, previous, results}).
    """
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200

    # Sans ?page ni ?page_size : pas de pagination (liste complète, attendue par le front).
    def paginate_queryset(self, queryset, request, view=None):
        if 'page' not in request.query_params and 'page_size' not in request.query_params:
            return None
        return super().paginate_queryset(queryset, request, view)
