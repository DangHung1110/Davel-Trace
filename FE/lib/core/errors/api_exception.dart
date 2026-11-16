enum ApiFailureCategory {
  validation,
  authentication,
  authorization,
  conflict,
  dependency,
  offline,
  unexpected,
}

class ApiException implements Exception {
  const ApiException(
    this.code,
    this.message, {
    this.statusCode,
    this.correlationId,
  });

  final String code;
  final String message;
  final int? statusCode;
  final String? correlationId;

  ApiFailureCategory get category {
    if (code == 'NETWORK_ERROR') return ApiFailureCategory.offline;
    if (statusCode == 401) return ApiFailureCategory.authentication;
    if (statusCode == 403) return ApiFailureCategory.authorization;
    if (statusCode == 409) return ApiFailureCategory.conflict;
    if (statusCode == 422 || code == 'VALIDATION_ERROR') {
      return ApiFailureCategory.validation;
    }
    if (statusCode == 503) return ApiFailureCategory.dependency;
    return ApiFailureCategory.unexpected;
  }

  @override
  String toString() => message;
}
