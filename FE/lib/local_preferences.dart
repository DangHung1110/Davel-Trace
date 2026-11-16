import 'package:shared_preferences/shared_preferences.dart';

class LocalPreferences {
  const LocalPreferences();

  Future<String?> activeProfileId() async {
    final preferences = await SharedPreferences.getInstance();
    return preferences.getString('davel_active_profile_id');
  }

  Future<void> setActiveProfileId(String id) async {
    final preferences = await SharedPreferences.getInstance();
    await preferences.setString('davel_active_profile_id', id);
  }

  Future<void> recordSuccessfulSync() async {
    final preferences = await SharedPreferences.getInstance();
    await preferences.setString(
      'davel_last_success_at',
      DateTime.now().toUtc().toIso8601String(),
    );
  }
}
