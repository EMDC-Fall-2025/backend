from django.http import JsonResponse

def csrf_failure(request, reason=""):
	# Standardized JSON for CSRF failures
	return JsonResponse(
		{
			"detail": "CSRF verification failed",
			"reason": reason or "Invalid or missing CSRF token",
			"path": request.path,
			"method": request.method,
		},
		status=403,
	)


