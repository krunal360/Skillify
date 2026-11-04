def admin_context(request):
    if request.user.is_authenticated and request.user.is_staff:
        try:
            from disputes.models import Dispute
            open_disputes = Dispute.objects.filter(
                status__in=['open', 'under_review']
            ).count()
        except Exception:
            open_disputes = 0
        return {'open_disputes': open_disputes}
    return {'open_disputes': 0}