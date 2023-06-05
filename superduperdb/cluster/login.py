from pinnacledb import CFG


def maybe_login_required(auth, service):
    """
    Require login depending on the contents of the config file.:w

    :param auth: basic auth instance
    :param service: name of the service on question
    """

    def decorator(f):
        if getattr(CFG, service).user:
            return auth.login_required(f)
        return f

    return decorator
