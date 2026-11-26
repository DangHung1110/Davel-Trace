import 'dart:async';

import 'package:flutter/material.dart';

import '../../../core/networking/api_client.dart';
import '../../../theme/app_theme.dart';
import '../../management/domain/models.dart';
import '../data/group_repository.dart';
import 'group_chat_screen.dart';
import 'group_expenses_screen.dart';
import 'group_people_screen.dart';
import 'group_plans_screen.dart';
import 'group_shared.dart';
import 'group_suggestions_screen.dart';

class GroupTripsScreen extends StatefulWidget {
  const GroupTripsScreen({
    super.key,
    required this.api,
    required this.ownedTrips,
    required this.openPlanning,
    this.createTrip,
    this.editTrip,
    this.openExpensesOnSelection = false,
  });

  final ApiClient api;
  final List<Trip> ownedTrips;
  final Future<void> Function(String tripId) openPlanning;
  final Future<Trip?> Function()? createTrip;
  final Future<void> Function(String tripId)? editTrip;
  final bool openExpensesOnSelection;

  @override
  State<GroupTripsScreen> createState() => _GroupTripsScreenState();
}

class _GroupTripsScreenState extends State<GroupTripsScreen> {
  late final _repository = GroupRepository(widget.api);
  late Future<List<Json>> _groups = _repository.list();
  bool _opening = false;

  Future<void> _refresh() async {
    final groups = _repository.list();
    setState(() => _groups = groups);
    try {
      await groups;
    } catch (_) {
      // FutureBuilder presents the load error.
    }
  }

  Future<void> _open(String tripId, [Json? initial]) async {
    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => GroupTripScreen(
          repository: _repository,
          tripId: tripId,
          initial: initial,
          openExpensesOnStart: widget.openExpensesOnSelection,
          onOpenPlanning: () => widget.openPlanning(tripId),
          onEditTrip: widget.editTrip == null
              ? null
              : () => widget.editTrip!(tripId),
        ),
      ),
    );
    if (mounted) await _refresh();
  }

  Future<void> _enable(Trip trip) async {
    if (!mounted || _opening) return;
    setState(() => _opening = true);
    try {
      final group = await _repository.enable(trip.id);
      if (mounted) await _open(trip.id, group);
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(groupError(error))));
      }
    } finally {
      if (mounted) setState(() => _opening = false);
    }
  }

  Future<void> _create() async {
    try {
      final trip = await widget.createTrip?.call();
      if (trip != null && mounted) await _enable(trip);
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(groupError(error))));
      }
    }
  }

  Future<void> _convert(List<Json> groups) async {
    final grouped = groups.map((group) => group['trip_id']).toSet();
    final trips = widget.ownedTrips
        .where(
          (trip) => trip.status == 'available' && !grouped.contains(trip.id),
        )
        .toList();
    if (trips.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Chưa có chuyến cá nhân để chuyển sang đi nhóm.'),
        ),
      );
      return;
    }
    final trip = await Navigator.of(context).push<Trip>(
      MaterialPageRoute(
        builder: (context) => Scaffold(
          appBar: AppBar(title: const Text('Chọn chuyến đã tạo')),
          body: SafeArea(
            child: ListView(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              children: [
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 16),
                  child: Text(
                    'Khi có người tham gia, họ sẽ xem được lịch và góp ý cho chuyến này.',
                  ),
                ),
                for (final trip in trips)
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: const Icon(Icons.route_outlined),
                    title: Text(trip.title),
                    subtitle: Text(groupDate(isoDate(trip.startDate))),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => Navigator.pop(context, trip),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
    if (trip != null && mounted) await _enable(trip);
  }

  Future<void> _join() async {
    final group = await Navigator.of(context).push<Json>(
      MaterialPageRoute(builder: (_) => _JoinGroup(repository: _repository)),
    );
    if (group != null && mounted) {
      await _open(textField(group, 'trip_id'), group);
    }
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<List<Json>>(
    future: _groups,
    builder: (context, snapshot) {
      final groups = snapshot.data ?? const [];
      final canCreate = widget.createTrip != null;
      return Scaffold(
        appBar: AppBar(
          title: const Text('Chuyến đi nhóm'),
          actions: [
            IconButton(
              onPressed: _refresh,
              tooltip: 'Tải lại chuyến nhóm',
              icon: const Icon(Icons.refresh),
            ),
          ],
        ),
        body: SafeArea(
          bottom: false,
          child: RefreshIndicator(
            onRefresh: _refresh,
            child: ListView(
              padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
              physics: const AlwaysScrollableScrollPhysics(),
              children: [
                if (snapshot.connectionState == ConnectionState.waiting)
                  const LinearProgressIndicator(),
                if (snapshot.hasError)
                  GroupProblem(
                    message: groupError(snapshot.error!),
                    onRetry: _refresh,
                  )
                else if (groups.isEmpty &&
                    snapshot.connectionState == ConnectionState.done) ...[
                  const SizedBox(height: 30),
                  Icon(
                    Icons.groups_outlined,
                    size: 44,
                    color: AppColors.primary,
                  ),
                  const SizedBox(height: 16),
                  Text(
                    'Cùng lên đường',
                    style: Theme.of(context).textTheme.headlineMedium,
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Tạo chuyến để mời bạn bè hoặc nhập mã mời bạn đã nhận.',
                    textAlign: TextAlign.center,
                  ),
                ],
                for (final trip in groups) ...[
                  ListTile(
                    key: ValueKey('open-group-${trip['trip_id']}'),
                    contentPadding: const EdgeInsets.symmetric(vertical: 6),
                    leading: const Icon(Icons.groups_outlined),
                    title: Text(
                      textField(trip, 'title'),
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    subtitle: Text(
                      '${groupDateRange(trip)}\n${groupRole(trip)} · ${integerField(trip, 'traveler_count')} người đi',
                    ),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: _opening
                        ? null
                        : () => _open(textField(trip, 'trip_id')),
                  ),
                  const Divider(height: 1),
                ],
              ],
            ),
          ),
        ),
        bottomNavigationBar: GroupActions(
          children: [
            FilledButton.icon(
              key: const Key('create-group-trip'),
              onPressed: _opening
                  ? null
                  : canCreate
                  ? _create
                  : () => _convert(groups),
              icon: const Icon(Icons.add),
              label: Text(canCreate ? 'Tạo chuyến nhóm' : 'Dùng chuyến đã tạo'),
            ),
            OutlinedButton(
              key: const Key('join-group-trip'),
              onPressed: _opening ? null : _join,
              child: const Text('Nhập mã tham gia'),
            ),
            if (canCreate && widget.ownedTrips.isNotEmpty)
              TextButton(
                onPressed: _opening ? null : () => _convert(groups),
                child: const Text('Dùng chuyến đã tạo'),
              ),
          ],
        ),
      );
    },
  );
}

class _JoinGroup extends StatefulWidget {
  const _JoinGroup({required this.repository});
  final GroupRepository repository;

  @override
  State<_JoinGroup> createState() => _JoinGroupState();
}

class _JoinGroupState extends State<_JoinGroup> {
  final _code = TextEditingController();
  final _name = TextEditingController();
  final _form = GlobalKey<FormState>();
  bool _busy = false;
  String? _error;

  Future<void> _submit() async {
    if (_busy || !(_form.currentState?.validate() ?? false)) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final group = await widget.repository.join(
        _code.text.trim(),
        _name.text.trim(),
      );
      if (mounted) Navigator.pop(context, group);
    } catch (error) {
      if (mounted) {
        setState(() {
          _busy = false;
          _error = groupError(error);
        });
      }
    }
  }

  @override
  void dispose() {
    _code.dispose();
    _name.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Tham gia chuyến nhóm')),
    body: SafeArea(
      child: Form(
        key: _form,
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            const Text('Dán mã do nhóm trưởng gửi cho bạn.'),
            const SizedBox(height: 16),
            TextFormField(
              key: const Key('group-invite-code'),
              controller: _code,
              decoration: const InputDecoration(labelText: 'Mã mời'),
              autocorrect: false,
              enableSuggestions: false,
              textInputAction: TextInputAction.next,
              validator: (value) =>
                  value == null || value.trim().isEmpty ? 'Nhập mã mời.' : null,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _name,
              maxLength: 80,
              textInputAction: TextInputAction.done,
              onFieldSubmitted: (_) => _submit(),
              decoration: const InputDecoration(
                labelText: 'Tên hiển thị (tùy chọn)',
                helperText: 'Tên này sẽ hiện với thành viên trong chuyến.',
              ),
            ),
            if (_error case final error?)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 8),
                child: Text(
                  error,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ),
            const SizedBox(height: 12),
            FilledButton(
              key: const Key('submit-group-join'),
              onPressed: _busy ? null : _submit,
              child: Text(_busy ? 'Đang tham gia…' : 'Tham gia chuyến'),
            ),
          ],
        ),
      ),
    ),
  );
}

class GroupTripScreen extends StatefulWidget {
  const GroupTripScreen({
    super.key,
    required this.repository,
    required this.tripId,
    required this.onOpenPlanning,
    this.onEditTrip,
    this.initial,
    this.openExpensesOnStart = false,
  });

  final GroupRepository repository;
  final String tripId;
  final Future<void> Function() onOpenPlanning;
  final Future<void> Function()? onEditTrip;
  final Json? initial;
  final bool openExpensesOnStart;

  @override
  State<GroupTripScreen> createState() => _GroupTripScreenState();
}

class _GroupTripScreenState extends State<GroupTripScreen> {
  late final _group = GroupState(
    widget.repository,
    widget.tripId,
    widget.initial,
  );
  Json? _plans;
  bool _readingPlans = false;

  @override
  void initState() {
    super.initState();
    unawaited(_refresh());
    if (widget.openExpensesOnStart) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) unawaited(_open(GroupExpensesScreen(group: _group)));
      });
    }
  }

  Future<void> _refresh() async {
    if (_readingPlans) return;
    _readingPlans = true;
    try {
      await _group.refresh();
      if (_group.detail != null) {
        final result = await widget.repository.get(widget.tripId, '/plans');
        if (mounted) setState(() => _plans = result);
      } else if (mounted) {
        setState(() => _plans = null);
      }
    } catch (_) {
      // The Plans page reports its own fetch failures and offers retry.
    } finally {
      _readingPlans = false;
    }
  }

  Future<void> _open(Widget child) async {
    final leftGroup = await Navigator.of(context)
        .push<bool>(MaterialPageRoute(builder: (_) => child));
    if (!mounted) return;
    if (leftGroup == true) {
      Navigator.pop(context);
    } else {
      await _refresh();
    }
  }

  Future<void> _editTrip() async {
    try {
      await widget.onEditTrip?.call();
      if (mounted) await _refresh();
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(groupError(error))));
      }
    }
  }

  @override
  void dispose() {
    _group.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => GroupPolling(
    onRefresh: _refresh,
    child: ListenableBuilder(
      listenable: _group,
      builder: (context, _) {
        final detail = _group.detail;
        final round = jsonObject(_plans?['round']);
        final options = jsonObjects(round['alternatives']).length;
        final active = jsonObject(_plans?['active']);
        return Scaffold(
          appBar: AppBar(
            title: const Text('Chuyến nhóm'),
            actions: [
              IconButton(
                onPressed: _refresh,
                tooltip: 'Cập nhật chuyến nhóm',
                icon: const Icon(Icons.refresh),
              ),
            ],
          ),
          body: SafeArea(
            child: detail == null && _group.failure == null
                ? const Center(child: CircularProgressIndicator())
                : RefreshIndicator(
                    onRefresh: _refresh,
                    child: ListView(
                      physics: const AlwaysScrollableScrollPhysics(),
                      padding: const EdgeInsets.fromLTRB(20, 8, 20, 28),
                      children: [
                        if (_group.failure case String failure)
                          GroupProblem(message: failure, onRetry: _refresh),
                        if (detail != null) ...[
                          Text(
                            textField(detail, 'title'),
                            style: Theme.of(context).textTheme.headlineLarge,
                          ),
                          const SizedBox(height: 8),
                          GroupStatus(
                            icon: Icons.calendar_today_outlined,
                            text: groupDateRange(detail),
                          ),
                          const SizedBox(height: 6),
                          GroupStatus(
                            icon: Icons.people_outline,
                            text:
                                '${integerField(detail, 'traveler_count')} người đi · ${groupRole(detail)}',
                          ),
                          const SizedBox(height: 24),
                          Material(
                            color: Theme.of(context)
                                .colorScheme
                                .primaryContainer,
                            borderRadius: BorderRadius.circular(14),
                            child: Padding(
                              padding: const EdgeInsets.all(16),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    options > 0
                                        ? 'Có phương án để góp ý'
                                        : active.isNotEmpty
                                        ? 'Lịch chung đã chốt'
                                        : 'Cùng chuẩn bị lịch',
                                    style: Theme.of(context)
                                        .textTheme
                                        .titleLarge,
                                  ),
                                  const SizedBox(height: 4),
                                  Text(
                                    options > 0
                                        ? '$options phương án đang mở để cả nhóm xem và bình chọn.'
                                        : active.isNotEmpty
                                        ? 'Xem các điểm dừng và lộ trình của nhóm.'
                                        : _group.isLeader
                                        ? 'Mời mọi người góp ý rồi tạo lịch cho cả chuyến.'
                                        : 'Gửi điểm bạn muốn ghé để nhóm trưởng đưa vào lịch.',
                                  ),
                                  const SizedBox(height: 12),
                                  FilledButton(
                                    key: const Key('open-group-plans'),
                                    onPressed: () => _open(
                                      GroupPlansScreen(
                                        group: _group,
                                        onOpenPlanning: widget.onOpenPlanning,
                                      ),
                                    ),
                                    child: Text(
                                      active.isNotEmpty || options > 0
                                          ? 'Xem lịch và phương án'
                                          : 'Mở lịch chung',
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                          const SizedBox(height: 20),
                          _GroupDestination(
                            destinationKey: 'open-group-suggestions',
                            icon: Icons.how_to_vote_outlined,
                            title: 'Góp ý chuyến đi',
                            caption: 'Đề xuất điểm ghé và điều cần lưu ý',
                            onTap: () =>
                                _open(GroupSuggestionsScreen(group: _group)),
                          ),
                          _GroupDestination(
                            destinationKey: 'open-group-chat',
                            icon: Icons.chat_bubble_outline,
                            title: 'Trò chuyện',
                            caption: 'Nhắn tin, gửi điểm hẹn và xem cập nhật',
                            onTap: () => _open(
                              GroupChatScreen(
                                group: _group,
                                onOpenPlans: () => _open(
                                  GroupPlansScreen(
                                    group: _group,
                                    onOpenPlanning: widget.onOpenPlanning,
                                  ),
                                ),
                              ),
                            ),
                          ),
                          _GroupDestination(
                            destinationKey: 'open-group-expenses',
                            icon: Icons.account_balance_wallet_outlined,
                            title: 'Quỹ và chi tiêu nhóm',
                            caption:
                                'Góp quỹ, ghi khoản chi và xem tiền ứng trước',
                            onTap: () =>
                                _open(GroupExpensesScreen(group: _group)),
                          ),
                          if (_group.isLeader &&
                              _group.canEdit &&
                              widget.onEditTrip != null)
                            _GroupDestination(
                              destinationKey: 'edit-group-trip',
                              icon: Icons.settings_outlined,
                              title: 'Cài đặt chuyến',
                              caption: 'Ngày, giờ, số người và ngân sách của cả nhóm',
                              onTap: _editTrip,
                            ),
                          _GroupDestination(
                            destinationKey: 'open-group-members',
                            icon: Icons.group_outlined,
                            title: 'Thành viên',
                            caption:
                                '${_group.members.length} người trong nhóm',
                            onTap: () =>
                                _open(GroupPeopleScreen(group: _group)),
                          ),
                        ],
                      ],
                    ),
                  ),
          ),
        );
      },
    ),
  );
}

class _GroupDestination extends StatelessWidget {
  const _GroupDestination({
    required this.destinationKey,
    required this.icon,
    required this.title,
    required this.caption,
    required this.onTap,
  });

  final String destinationKey;
  final IconData icon;
  final String title;
  final String caption;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Column(
    children: [
      ListTile(
        key: ValueKey(destinationKey),
        contentPadding: const EdgeInsets.symmetric(vertical: 4),
        leading: Icon(icon, color: AppColors.primary),
        title: Text(title, style: Theme.of(context).textTheme.titleMedium),
        subtitle: Text(caption),
        trailing: const Icon(Icons.chevron_right),
        onTap: onTap,
      ),
      const Divider(height: 1),
    ],
  );
}
