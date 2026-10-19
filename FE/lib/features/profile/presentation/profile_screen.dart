import 'package:flutter/material.dart';

import '../../../app_state.dart';
import '../../../shared/widgets/app_header.dart';
import '../../../shared/widgets/surface_card.dart';
import '../../../theme/app_theme.dart';
import '../../management/domain/models.dart';

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key, required this.state, this.onReady});

  final AppState state;
  final VoidCallback? onReady;

  Future<void> _openEditor(BuildContext context, {UserProfile? profile}) async {
    final data = await showModalBottomSheet<Map<String, dynamic>>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      useSafeArea: true,
      builder: (_) => ProfileEditor(profile: profile),
    );
    if (data == null || !context.mounted) return;
    try {
      if (profile == null) {
        await state.createProfile(data);
      } else {
        await state.updateActiveProfile(data);
      }
      onReady?.call();
    } catch (_) {
      if (context.mounted) _showError(context, state.errorMessage);
    }
  }

  Future<void> _delete(BuildContext context) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Xóa hồ sơ?'),
        content: const Text(
          'Các chuyến đi và khoản chi thuộc hồ sơ này cũng sẽ bị xóa.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Hủy'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Xóa'),
          ),
        ],
      ),
    );
    if (confirmed != true || !context.mounted) return;
    try {
      await state.deleteActiveProfile();
    } catch (_) {
      if (context.mounted) _showError(context, state.errorMessage);
    }
  }

  @override
  Widget build(BuildContext context) {
    final profile = state.activeProfile;
    if (profile == null) {
      return ProfileOnboarding(
        busy: state.isMutating,
        onSubmit: (data) async {
          await state.createProfile(data);
          onReady?.call();
        },
      );
    }
    return ColoredBox(
      color: AppColors.canvas,
      child: Column(
        children: [
          AppHeader(
            compact: true,
            section: 'Hồ sơ',
            trailing: IconButton(
              tooltip: 'Thêm hồ sơ',
              onPressed: state.isMutating ? null : () => _openEditor(context),
              icon: const Icon(Icons.person_add_alt_1_outlined),
            ),
          ),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.fromLTRB(16, 14, 16, 24),
              children: [
                Text(
                  'Chào ${profile.displayName}',
                  style: Theme.of(context).textTheme.headlineMedium,
                ),
                const SizedBox(height: 4),
                const Text(
                  'Hồ sơ local giúp tách chuyến đi cho nhiều người dùng trên cùng thiết bị.',
                ),
                const SizedBox(height: 18),
                if (state.profiles.length > 1) ...[
                  DropdownButtonFormField<String>(
                    key: const Key('profile-switcher'),
                    initialValue: profile.id,
                    decoration: const InputDecoration(
                      labelText: 'Hồ sơ đang dùng',
                    ),
                    items: state.profiles
                        .map(
                          (item) => DropdownMenuItem(
                            value: item.id,
                            child: Text(item.displayName),
                          ),
                        )
                        .toList(),
                    onChanged: state.isMutating
                        ? null
                        : (id) {
                            if (id == null) return;
                            state.selectProfile(
                              state.profiles.firstWhere(
                                (item) => item.id == id,
                              ),
                            );
                          },
                  ),
                  const SizedBox(height: 14),
                ],
                SurfaceCard(
                  child: Column(
                    children: [
                      const CircleAvatar(
                        radius: 30,
                        backgroundColor: AppColors.sand,
                        child: Icon(
                          Icons.person_outline_rounded,
                          color: AppColors.primary,
                          size: 30,
                        ),
                      ),
                      const SizedBox(height: 10),
                      Text(
                        profile.displayName,
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      const SizedBox(height: 12),
                      _ProfileRow(
                        label: 'Kiểu nhóm',
                        value: _party(profile.partyType),
                      ),
                      _ProfileRow(
                        label: 'Mục đích',
                        value: _purpose(profile.tripPurpose),
                      ),
                      _ProfileRow(label: 'Nhịp đi', value: '${profile.pace}/3'),
                      _ProfileRow(
                        label: 'Mức chi',
                        value: '${profile.spendingLevel}/3',
                      ),
                      _ProfileRow(
                        label: 'Ẩm thực',
                        value: profile.foodPreferences.isEmpty
                            ? 'Chưa đặt'
                            : profile.foodPreferences.join(', '),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 14),
                OutlinedButton.icon(
                  key: const Key('edit-profile-button'),
                  onPressed: state.isMutating
                      ? null
                      : () => _openEditor(context, profile: profile),
                  icon: const Icon(Icons.edit_outlined),
                  label: const Text('Chỉnh sửa hồ sơ'),
                ),
                const SizedBox(height: 8),
                TextButton.icon(
                  onPressed: state.isMutating ? null : () => _delete(context),
                  icon: const Icon(
                    Icons.delete_outline,
                    color: AppColors.error,
                  ),
                  label: const Text(
                    'Xóa hồ sơ',
                    style: TextStyle(color: AppColors.error),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class ProfileOnboarding extends StatelessWidget {
  const ProfileOnboarding({
    super.key,
    required this.onSubmit,
    required this.busy,
  });

  final Future<void> Function(Map<String, dynamic>) onSubmit;
  final bool busy;

  @override
  Widget build(BuildContext context) => ColoredBox(
    color: AppColors.canvas,
    child: SafeArea(
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 440),
          child: ListView(
            padding: const EdgeInsets.fromLTRB(20, 28, 20, 24),
            children: [
              const Icon(
                Icons.explore_outlined,
                size: 46,
                color: AppColors.primary,
              ),
              const SizedBox(height: 22),
              const Text(
                'DAVEL TRACE · MANAGEMENT MVP',
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: AppColors.accent,
                  fontSize: 11,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 1,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'Bắt đầu từ hồ sơ của bạn',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.displaySmall,
              ),
              const SizedBox(height: 8),
              const Text(
                'Tạo hồ sơ local để quản lý chuyến đi, lịch thủ công và chi tiêu. Không cần đăng nhập.',
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 22),
              SurfaceCard(
                child: ProfileEditor(
                  key: ProfileEditor.inlineKey,
                  inline: true,
                ),
              ),
              const SizedBox(height: 12),
              FilledButton(
                key: const Key('create-first-profile-button'),
                onPressed: busy
                    ? null
                    : () async {
                        final form = ProfileEditor.inlineKey.currentState;
                        final data = form?.submit();
                        if (data == null) return;
                        try {
                          await onSubmit(data);
                        } catch (_) {
                          if (context.mounted) {
                            _showError(
                              context,
                              'Không thể lưu hồ sơ. Kiểm tra backend rồi thử lại.',
                            );
                          }
                        }
                      },
                child: Text(busy ? 'Đang lưu…' : 'Tạo hồ sơ & tiếp tục'),
              ),
            ],
          ),
        ),
      ),
    ),
  );
}

class ProfileEditor extends StatefulWidget {
  const ProfileEditor({super.key, this.profile, this.inline = false});

  static final inlineKey = GlobalKey<ProfileEditorState>();

  final UserProfile? profile;
  final bool inline;

  @override
  State<ProfileEditor> createState() => ProfileEditorState();
}

class ProfileEditorState extends State<ProfileEditor> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _name;
  late final TextEditingController _food;
  late String _party;
  late String _purpose;
  late double _pace;
  late double _spending;

  @override
  void initState() {
    super.initState();
    final profile = widget.profile;
    _name = TextEditingController(text: profile?.displayName ?? '');
    _food = TextEditingController(
      text: profile?.foodPreferences.join(', ') ?? '',
    );
    _party = profile?.partyType ?? 'solo';
    _purpose = profile?.tripPurpose ?? 'leisure';
    _pace = (profile?.pace ?? 2).toDouble();
    _spending = (profile?.spendingLevel ?? 2).toDouble();
  }

  @override
  void dispose() {
    _name.dispose();
    _food.dispose();
    super.dispose();
  }

  Map<String, dynamic>? submit() {
    if (!_formKey.currentState!.validate()) return null;
    return {
      'display_name': _name.text.trim(),
      'language': 'vi',
      'party_type': _party,
      'trip_purpose': _purpose,
      'spending_level': _spending.round(),
      'pace': _pace.round(),
      'fitness': 2,
      'food_preferences': _food.text
          .split(',')
          .map((item) => item.trim())
          .where((item) => item.isNotEmpty)
          .toList(),
      'must_avoid': <String>[],
    };
  }

  @override
  Widget build(BuildContext context) {
    final form = Form(
      key: _formKey,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (!widget.inline) ...[
            Text(
              widget.profile == null ? 'Hồ sơ mới' : 'Chỉnh sửa hồ sơ',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 14),
          ],
          TextFormField(
            key: const Key('profile-name-field'),
            controller: _name,
            decoration: const InputDecoration(labelText: 'Tên hiển thị'),
            validator: (value) => value == null || value.trim().isEmpty
                ? 'Nhập tên hiển thị'
                : null,
          ),
          const SizedBox(height: 10),
          DropdownButtonFormField<String>(
            initialValue: _party,
            decoration: const InputDecoration(labelText: 'Bạn thường đi'),
            items: const [
              DropdownMenuItem(value: 'solo', child: Text('Một mình')),
              DropdownMenuItem(value: 'couple', child: Text('Cặp đôi')),
              DropdownMenuItem(value: 'family', child: Text('Gia đình')),
              DropdownMenuItem(value: 'friends', child: Text('Nhóm bạn')),
            ],
            onChanged: (value) => setState(() => _party = value!),
          ),
          const SizedBox(height: 10),
          DropdownButtonFormField<String>(
            initialValue: _purpose,
            decoration: const InputDecoration(labelText: 'Mục đích chính'),
            items: const [
              DropdownMenuItem(value: 'leisure', child: Text('Nghỉ dưỡng')),
              DropdownMenuItem(value: 'discovery', child: Text('Khám phá')),
              DropdownMenuItem(value: 'food', child: Text('Ẩm thực')),
              DropdownMenuItem(value: 'business', child: Text('Công tác')),
            ],
            onChanged: (value) => setState(() => _purpose = value!),
          ),
          const SizedBox(height: 10),
          TextFormField(
            controller: _food,
            decoration: const InputDecoration(
              labelText: 'Món yêu thích',
              hintText: 'mì Quảng, hải sản',
            ),
          ),
          const SizedBox(height: 10),
          Text(
            'Nhịp đi · ${_pace.round()}/3',
            style: const TextStyle(fontWeight: FontWeight.w700),
          ),
          Slider(
            value: _pace,
            min: 1,
            max: 3,
            divisions: 2,
            onChanged: (value) => setState(() => _pace = value),
          ),
          Text(
            'Mức chi · ${_spending.round()}/3',
            style: const TextStyle(fontWeight: FontWeight.w700),
          ),
          Slider(
            value: _spending,
            min: 1,
            max: 3,
            divisions: 2,
            onChanged: (value) => setState(() => _spending = value),
          ),
        ],
      ),
    );
    if (widget.inline) {
      return form;
    }
    return Padding(
      padding: EdgeInsets.fromLTRB(
        18,
        4,
        18,
        MediaQuery.viewInsetsOf(context).bottom + 18,
      ),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            form,
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                key: const Key('save-profile-button'),
                onPressed: () {
                  final data = submit();
                  if (data != null) Navigator.pop(context, data);
                },
                child: const Text('Lưu hồ sơ'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ProfileRow extends StatelessWidget {
  const _ProfileRow({required this.label, required this.value});
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 7),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 90,
          child: Text(
            label,
            style: const TextStyle(color: AppColors.muted, fontSize: 12),
          ),
        ),
        Expanded(
          child: Text(
            value,
            textAlign: TextAlign.right,
            style: const TextStyle(fontWeight: FontWeight.w700),
          ),
        ),
      ],
    ),
  );
}

String _party(String value) => switch (value) {
  'couple' => 'Cặp đôi',
  'family' => 'Gia đình',
  'friends' => 'Nhóm bạn',
  _ => 'Một mình',
};

String _purpose(String value) => switch (value) {
  'discovery' => 'Khám phá',
  'food' => 'Ẩm thực',
  'business' => 'Công tác',
  _ => 'Nghỉ dưỡng',
};

void _showError(BuildContext context, String? message) {
  ScaffoldMessenger.of(context).showSnackBar(
    SnackBar(content: Text(message ?? 'Không thể hoàn tất thao tác.')),
  );
}
