class AccountSummary {
  const AccountSummary({
    required this.id,
    required this.email,
    required this.status,
    required this.roles,
    this.activeSessionCount = 0,
  });

  factory AccountSummary.fromJson(Map<String, dynamic> json) => AccountSummary(
    id: json['account_id'] as String,
    email: json['email'] as String,
    status: json['status'] as String,
    roles: (json['roles'] as List<dynamic>? ?? const []).cast<String>(),
    activeSessionCount: json['active_session_count'] as int? ?? 0,
  );

  final String id;
  final String email;
  final String status;
  final List<String> roles;
  final int activeSessionCount;
}

class AuthTokens {
  const AuthTokens({
    required this.account,
    required this.accessToken,
    required this.refreshToken,
  });

  factory AuthTokens.fromJson(Map<String, dynamic> json) => AuthTokens(
    account: AccountSummary.fromJson(json['account'] as Map<String, dynamic>),
    accessToken: json['access_token'] as String,
    refreshToken: json['refresh_token'] as String,
  );

  final AccountSummary account;
  final String accessToken;
  final String refreshToken;
}

class IdentitySession {
  const IdentitySession({
    required this.id,
    required this.deviceLabel,
    required this.current,
  });

  factory IdentitySession.fromJson(Map<String, dynamic> json) =>
      IdentitySession(
        id: json['session_id'] as String,
        deviceLabel: json['device_label'] as String,
        current: json['current'] as bool? ?? false,
      );

  final String id;
  final String deviceLabel;
  final bool current;
}
