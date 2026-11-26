import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../data/group_repository.dart';
import 'group_shared.dart';

class GroupPeopleScreen extends StatefulWidget {
  const GroupPeopleScreen({super.key, required this.group});
  final GroupState group;

  @override
  State<GroupPeopleScreen> createState() => _GroupPeopleScreenState();
}

class _GroupPeopleScreenState extends State<GroupPeopleScreen> {
  GroupState get group => widget.group;
  List<Json> _invites = const [];
  bool _busy = false;
  String? _inviteFailure;

  @override
  void initState() {
    super.initState();
    unawaited(_refresh());
  }

  Future<void> _refresh() async {
    await group.refresh();
    if (!mounted || !group.isLeader) return;
    try {
      final result = await group.repository.get(group.tripId, '/invites');
      if (mounted) {
        setState(() {
          _invites = jsonObjects(result['items']);
          _inviteFailure = null;
        });
      }
    } catch (error) {
      if (mounted) setState(() => _inviteFailure = groupError(error));
    }
  }

  Future<void> _run(Future<void> Function() action) async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      await action();
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(groupError(error))));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _invite() => _run(() async {
    final invite = await group.repository.post(group.tripId, '/invites');
    if (!mounted) return;
    final code = textField(invite, 'code');
    await showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        scrollable: true,
        title: const Text('Mã mời tham gia'),
        content: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            SelectableText(
              code,
              key: const Key('created-group-invite'),
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 12),
            const Text(
              'Gửi mã riêng cho người bạn muốn mời. Mỗi mã dùng được một lần.',
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Đóng'),
          ),
          FilledButton(
            onPressed: () async {
              await Clipboard.setData(ClipboardData(text: code));
              if (context.mounted) {
                Navigator.pop(context);
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Đã sao chép mã mời.')),
                );
              }
            },
            child: const Text('Sao chép mã'),
          ),
        ],
      ),
    );
    if (mounted) await _refresh();
  });

  Future<void> _guest() async {
    String name = '';
    final selected = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        scrollable: true,
        title: const Text('Thêm người đi cùng'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text(
              'Dành cho người đi cùng không dùng app. Bạn có thể nhập góp ý và ghi khoản chia cho họ.',
            ),
            const SizedBox(height: 12),
            TextField(
              key: const Key('group-guest-name'),
              maxLength: 80,
              decoration: const InputDecoration(labelText: 'Tên người đi cùng'),
              onChanged: (value) => name = value.trim(),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Quay lại'),
          ),
          FilledButton(
            onPressed: () {
              if (name.isNotEmpty) Navigator.pop(context, name);
            },
            child: const Text('Thêm người'),
          ),
        ],
      ),
    );
    if (selected == null || !mounted) return;
    await _run(() async {
      group.update(
        await group.repository.post(group.tripId, '/guests', {
          'display_name': selected,
        }),
      );
    });
  }

  Future<void> _remove(Json member) async {
    final id = textField(member, 'id');
    final leaving = id == group.memberId;
    final agreed = await confirmGroupAction(
      context,
      title: leaving ? 'Rời chuyến đi?' : 'Ngừng quyền tham gia?',
      description: leaving
          ? 'Bạn sẽ mất quyền xem lịch và trò chuyện. Các khoản chia đã ghi vẫn được giữ.'
          : '${textField(member, 'display_name')} sẽ mất quyền tham gia. Các khoản chia đã ghi vẫn được giữ.',
      action: leaving ? 'Rời chuyến' : 'Ngừng quyền',
    );
    if (!agreed || !mounted) return;
    await _run(() async {
      await group.repository.delete(group.tripId, '/members/$id');
      if (!mounted) return;
      if (leaving) {
        Navigator.pop(context, true);
      } else {
        await _refresh();
      }
    });
  }

  Future<void> _revoke(Json invite) async {
    final confirmed = await confirmGroupAction(
      context,
      title: 'Thu hồi lời mời?',
      description: 'Người đã nhận mã sẽ không thể dùng mã này để tham gia.',
      action: 'Thu hồi mã',
    );
    if (!confirmed || !mounted) return;
    await _run(() async {
      await group.repository.delete(group.tripId, '/invites/${invite['id']}');
      if (mounted) await _refresh();
    });
  }

  @override
  Widget build(BuildContext context) => GroupPolling(
    onRefresh: _refresh,
    child: ListenableBuilder(
      listenable: group,
      builder: (context, _) {
        final isLeader = group.isLeader;
        final active = _invites.where((invite) => invite['status'] == 'active');
        final me = group.members
            .where((person) => person['id'] == group.memberId)
            .firstOrNull;
        return Scaffold(
          appBar: AppBar(title: const Text('Thành viên')),
          body: SafeArea(
            bottom: false,
            child: RefreshIndicator(
              onRefresh: _refresh,
              child: ListView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
                children: [
                  if (group.failure case String failure)
                    GroupProblem(message: failure, onRetry: _refresh),
                  if (group.detail != null) ...[
                    Text(
                      'Người đi cùng',
                      style: Theme.of(context).textTheme.headlineSmall,
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      'Người đi thực tế được tính theo thông tin chuyến đi, kể cả người chưa tham gia app.',
                    ),
                    const SizedBox(height: 12),
                    for (final person in group.members)
                      ListTile(
                        key: ValueKey('group-member-${person['id']}'),
                        contentPadding: EdgeInsets.zero,
                        leading: Icon(
                          person['is_guest'] == true
                              ? Icons.person_outline
                              : Icons.person_2_outlined,
                        ),
                        title: Text(textField(person, 'display_name')),
                        subtitle: Text(
                          '${groupRole(person)}${person['id'] == group.memberId ? ' · Bạn' : ''}',
                        ),
                        trailing:
                            !isLeader ||
                                !group.canEdit ||
                                person['id'] == group.memberId
                            ? null
                            : PopupMenuButton<String>(
                                tooltip:
                                    'Quản lý ${textField(person, 'display_name')}',
                                onSelected: (_) => _remove(person),
                                itemBuilder: (_) => const [
                                  PopupMenuItem(
                                    value: 'remove',
                                    child: Text('Ngừng quyền tham gia'),
                                  ),
                                ],
                              ),
                      ),
                    if (isLeader) ...[
                      const SizedBox(height: 18),
                      Text(
                        'Mã mời đang mở',
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      const SizedBox(height: 6),
                      if (_inviteFailure case String failure)
                        GroupProblem(message: failure, onRetry: _refresh)
                      else if (active.isEmpty)
                        const Text('Chưa có mã đang chờ sử dụng.'),
                      for (final invite in active)
                        ListTile(
                          contentPadding: EdgeInsets.zero,
                          leading: const Icon(Icons.key_outlined),
                          title: Text(
                            'Hết hạn ${groupDate(textField(invite, 'expires_at'))}',
                          ),
                          subtitle: const Text(
                            'Gửi mã mới nếu người nhận không còn giữ mã.',
                          ),
                          trailing: IconButton(
                            onPressed: _busy || !group.canEdit
                                ? null
                                : () => _revoke(invite),
                            tooltip: 'Thu hồi mã mời',
                            icon: const Icon(Icons.cancel_outlined),
                          ),
                        ),
                    ] else if (me != null) ...[
                      const SizedBox(height: 16),
                      Align(
                        alignment: Alignment.centerLeft,
                        child: TextButton(
                          onPressed: _busy ? null : () => _remove(me),
                          child: const Text('Rời chuyến'),
                        ),
                      ),
                    ],
                  ],
                ],
              ),
            ),
          ),
          bottomNavigationBar: !isLeader || !group.canEdit
              ? null
              : GroupActions(
                  children: [
                    FilledButton.icon(
                      key: const Key('create-group-invite'),
                      onPressed: _busy ? null : _invite,
                      icon: const Icon(Icons.person_add_alt_1_outlined),
                      label: const Text('Tạo mã mời'),
                    ),
                    OutlinedButton(
                      key: const Key('add-group-guest'),
                      onPressed: _busy ? null : _guest,
                      child: const Text('Thêm người không dùng app'),
                    ),
                  ],
                ),
        );
      },
    ),
  );
}
