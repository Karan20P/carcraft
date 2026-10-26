def notifications(request):
    if not request.user.is_authenticated:
        return {}
    return {"unread_notifications": request.user.notifications.filter(is_read=False).count()}
