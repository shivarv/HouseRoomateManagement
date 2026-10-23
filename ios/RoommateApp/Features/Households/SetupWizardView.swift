import SwiftUI

/// Guided set-up of a new home: your home (with how many of each), roommates, chores, groceries,
/// bills, review. Everything is prefilled from the server's template; nothing is created until
/// "Create home". Mirrors web SetupWizardPage.tsx.
struct SetupWizardView: View {
    var onCreated: (Household) -> Void = { _ in }
    @Environment(\.dismiss) private var dismiss
    @Environment(Session.self) private var session
    @State private var template: SetupTemplate?
    @State private var loadError: String?

    var body: some View {
        NavigationStack {
            Group {
                if let template {
                    WizardSteps(template: template, me: session.user?.name ?? "You") { house in
                        session.rememberHousehold(house.id)
                        onCreated(house)
                        dismiss()
                    }
                } else if let loadError {
                    ContentUnavailableView("Couldn't load the template", systemImage: "exclamationmark.triangle", description: Text(loadError))
                } else {
                    ProgressView()
                }
            }
            .navigationTitle("Set up a new home")
            .navigationBarTitleDisplayMode(.inline)
        }
        .task {
            do { template = try await APIClient.shared.setupTemplate() } catch { loadError = error.localizedDescription }
        }
    }
}

private enum Step: String, CaseIterable {
    case home = "Your home", roommates = "Roommates", chores = "Chores", groceries = "Groceries", bills = "Bills", review = "Review"
}

/// A chore as the wizard edits it: who's left out of its turns, by position in `people` (0 = me).
private struct WizardChore: Hashable {
    var chore: SetupChore
    var excluded: Set<Int> = []
}

private struct WizardSteps: View {
    let template: SetupTemplate
    let me: String
    let onCreated: (Household) -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var step: Step = .home
    @State private var name = ""
    @State private var address = ""
    @State private var timezone = TimeZone.current.identifier
    // How many of each to start with. Roommates and groceries can be 0; chores and bills start at 1.
    @State private var roommateCount = 2
    @State private var choreCount = 2
    @State private var groceryCount = 0
    @State private var billCount = 2
    @State private var roommates: [String] = []
    @State private var chores: [WizardChore] = []
    @State private var groceries: [SetupGrocery] = []
    @State private var bills: [SetupBill] = []
    @State private var amounts: [String] = []  // typed amounts, one per bill
    @State private var currency = "USD"
    @State private var ownGrocery = ""
    @State private var ownGroceryType = "groceries"
    @State private var error: String?
    @State private var creating = false
    @State private var confirmCancel = false

    private var max: Int { template.maxItems }
    private var people: [String] { [me] + roommates.map { $0.trimmingCharacters(in: .whitespaces) } }

    /// No roommates skips their step. Groceries always shows, so items can still be added there.
    private var steps: [Step] {
        Step.allCases.filter { $0 != .roommates || roommateCount > 0 }
    }
    private var index: Int { steps.firstIndex(of: step) ?? 0 }
    private var touched: Bool { step != .home || !name.isEmpty || !address.isEmpty }

    var body: some View {
        Form {
            Section {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 6) {
                        ForEach(Array(steps.enumerated()), id: \.element) { i, s in
                            Text((i < index ? "✓ " : "\(i + 1) ") + s.rawValue)
                                .font(.caption.weight(.semibold))
                                .padding(.horizontal, 9).padding(.vertical, 4)
                                .background(i == index ? Color.accentColor : i < index ? Color.green.opacity(0.15) : Color.secondary.opacity(0.1), in: Capsule())
                                .foregroundStyle(i == index ? Color.white : i < index ? Color.green : Color.secondary)
                        }
                    }
                }
            }
            .listRowBackground(Color.clear)
            .listRowInsets(EdgeInsets())

            switch step {
            case .home: homeStep
            case .roommates: roommatesStep
            case .chores: choresStep
            case .groceries: groceriesStep
            case .bills: billsStep
            case .review: reviewStep
            }

            if let error {
                Section { ErrorBanner(message: error) }
            }
        }
        .toolbar {
            ToolbarItem(placement: .cancellationAction) {
                Button("Cancel") { if touched { confirmCancel = true } else { dismiss() } }
            }
            ToolbarItem(placement: .confirmationAction) {
                if step == .review {
                    Button(creating ? "Creating…" : "Create") { Task { await create() } }.disabled(creating)
                } else {
                    Button("Next") { next() }
                }
            }
            ToolbarItem(placement: .bottomBar) {
                if index > 0 { Button("← Back") { error = nil; step = steps[index - 1] }.disabled(creating) }
            }
        }
        .interactiveDismissDisabled(touched)
        .confirmationDialog("Your new home isn't created yet", isPresented: $confirmCancel, titleVisibility: .visible) {
            Button("Leave and lose my changes", role: .destructive) { dismiss() }
            Button("Keep setting up", role: .cancel) {}
        } message: {
            Text("Finish the setup and tap “Create” to save it, or you'll lose what you've filled in.")
        }
    }

    // MARK: Steps

    @ViewBuilder private var homeStep: some View {
        Section {
            TextField("Name, e.g. Maple Street House", text: $name)
            TextField("Address, e.g. 12 Maple St, Boston, MA", text: $address).textContentType(.fullStreetAddress)
            TextField("Timezone", text: $timezone).textInputAutocapitalization(.never).autocorrectionDisabled()
        } header: {
            Text("🏠 Your new home")
        } footer: {
            Text("You'll be its admin.")
        }
        Section {
            question("👥 Roommates living with you", value: $roommateCount, range: 0...(max - 1),
                     hint: roommateCount == 0 ? "Just you for now — invite people later with the invite code." : "Not counting you.")
            question("🧹 Chores to start with", value: $choreCount, range: 1...max, hint: "At least one.")
            question("🛒 Grocery quick-add items", value: $groceryCount, range: 0...max,
                     hint: groceryCount == 0 ? "None for now — anyone can still add anything." : "One-tap buttons for things you buy often.")
            question("🧾 Bills to remind you about", value: $billCount, range: 1...max, hint: "At least one, like rent or WiFi.")
        } header: {
            Text("How many to start with")
        } footer: {
            Text("The next steps are prefilled with that many. Change anything along the way, or later in Settings.")
        }
    }

    private func question(_ title: String, value: Binding<Int>, range: ClosedRange<Int>, hint: String) -> some View {
        Picker(selection: value) {
            ForEach(Array(range), id: \.self) { Text("\($0)").tag($0) }
        } label: {
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                Text(hint).font(.caption).foregroundStyle(.secondary)
            }
        }
    }

    private var roommatesStep: some View {
        Section {
            HStack {
                Text(me)
                Spacer()
                Badge(text: "You · admin", color: .accentColor)
            }
            ForEach(roommates.indices, id: \.self) { i in
                TextField("Roommate \(i + 2)", text: $roommates[i])
            }
        } header: {
            Text("👥 Roommates")
        } footer: {
            Text("They can claim their name later with the invite code, or stay name-only.")
        }
    }

    private var choresStep: some View {
        ForEach(chores.indices, id: \.self) { i in
            Section {
                TextField("Chore, e.g. Clean bathroom", text: $chores[i].chore.name)
                Picker("How often", selection: $chores[i].chore.frequency) {
                    Text("Daily").tag(Frequency.daily)
                    Text("Weekly").tag(Frequency.weekly)
                }
                Picker("Who does it", selection: $chores[i].chore.assignmentMode) {
                    Text("Take turns").tag(AssignmentMode.rotation)
                    Text("Anyone").tag(AssignmentMode.open)
                }
                if chores[i].chore.assignmentMode == .rotation {
                    DisclosureGroup {
                        ForEach(people.indices, id: \.self) { p in
                            Toggle(people[p], isOn: Binding(
                                get: { !chores[i].excluded.contains(p) },
                                set: { on in if on { chores[i].excluded.remove(p) } else { chores[i].excluded.insert(p) } }
                            ))
                        }
                    } label: {
                        Label(rotationLabel(chores[i].excluded), systemImage: "person.2")
                            .foregroundStyle(chores[i].excluded.isEmpty ? Color.green : Color.orange)
                    }
                }
            } header: {
                if i == 0 { Text("🧹 Chores — take turns rotates; anyone logs it") }
            }
        }
    }

    @ViewBuilder private var groceriesStep: some View {
        Section {
            if groceries.isEmpty {
                Text("Nothing yet — that's fine. Pick some below, or add them later in Settings → Groceries.")
                    .foregroundStyle(.secondary)
            }
            ForEach(groceries, id: \.self) { g in
                Text("\(categoryIcon(g.categoryKey)) \(g.name)")
                    .swipeActions { Button("Remove", role: .destructive) { setGroceries(groceries.filter { $0 != g }) } }
            }
        } header: {
            Text("🛒 Your list · \(groceries.count) of \(max)")
        } footer: {
            Text("One-tap buttons on Groceries. Swipe to remove. Anyone can still add anything to the list.")
        }

        Section("Pick from our list") {
            ForEach(template.groceries, id: \.self) { option in
                let on = hasGrocery(option.name)
                Button {
                    if on {
                        setGroceries(groceries.filter { $0.name.lowercased() != option.name.lowercased() })
                    } else if groceries.count < max {
                        setGroceries(groceries + [option])
                    }
                } label: {
                    HStack {
                        Text("\(categoryIcon(option.categoryKey)) \(option.name)").foregroundStyle(.primary)
                        Spacer()
                        Image(systemName: on ? "checkmark.circle.fill" : "plus.circle")
                            .foregroundStyle(on ? Color.accentColor : Color.secondary)
                    }
                }
                .disabled(!on && groceries.count >= max)
            }
        }

        Section {
            HStack {
                TextField("e.g. Paneer", text: $ownGrocery)
                Picker("Type", selection: $ownGroceryType) {
                    ForEach(template.categories) { Text("\($0.icon) \($0.label)").tag($0.key) }
                }
                .labelsHidden()
                .fixedSize()
            }
            Button("Add", systemImage: "plus") {
                let name = ownGrocery.trimmingCharacters(in: .whitespaces)
                if hasGrocery(name) { error = "\(name) is already on your list"; return }
                setGroceries(groceries + [SetupGrocery(name: name, categoryKey: ownGroceryType)])
                ownGrocery = ""
                error = nil
            }
            .disabled(ownGrocery.trimmingCharacters(in: .whitespaces).isEmpty || groceries.count >= max)
        } header: {
            Text("Add your own")
        }
    }

    private func categoryIcon(_ key: String) -> String {
        template.categories.first { $0.key == key }?.icon ?? "🛍️"
    }

    private func hasGrocery(_ name: String) -> Bool {
        let wanted = name.trimmingCharacters(in: .whitespaces).lowercased()
        return groceries.contains { $0.name.trimmingCharacters(in: .whitespaces).lowercased() == wanted }
    }

    /// The count follows, so going back to "Your home" keeps these items.
    private func setGroceries(_ list: [SetupGrocery]) {
        groceries = list
        groceryCount = list.count
    }

    @ViewBuilder private var billsStep: some View {
        ForEach(bills.indices, id: \.self) { i in
            Section {
                HStack {
                    TextField("🧾", text: $bills[i].icon).frame(width: 44).multilineTextAlignment(.center)
                    TextField("Bill, e.g. WiFi", text: $bills[i].name)
                }
                Picker("Who pays", selection: Binding(get: { bills[i].payerMode }, set: { mode in
                    bills[i].payerMode = mode
                    bills[i].payerName = mode == .one ? (bills[i].payerName ?? me) : nil
                })) {
                    ForEach(PayerMode.allCases) { Text($0.label).tag($0) }
                }
                if bills[i].payerMode == .one {
                    Picker("Person", selection: Binding(get: { bills[i].payerName ?? me }, set: { bills[i].payerName = $0 })) {
                        ForEach(people, id: \.self) { Text($0).tag($0) }
                    }
                }
                Picker("Repeats", selection: Binding(get: { bills[i].frequency }, set: { f in
                    bills[i].frequency = f
                    if f == .weekly && bills[i].dueDay > 7 { bills[i].dueDay = 1 }
                })) {
                    ForEach(BillFrequency.allCases) { Text($0.label).tag($0) }
                }
                switch bills[i].frequency {
                case .monthly:
                    Picker("Due", selection: Binding(get: { bills[i].dueDay > 28 ? Bill.lastDay : bills[i].dueDay }, set: { bills[i].dueDay = $0 })) {
                        ForEach(1...28, id: \.self) { Text("\($0)").tag($0) }
                        Text("Last day of month").tag(Bill.lastDay)
                    }
                case .weekly:
                    Picker("Due", selection: $bills[i].dueDay) {
                        ForEach(1...7, id: \.self) { Text(Bill.weekdays[$0 - 1]).tag($0) }
                    }
                case .daily:
                    Text("Due the same day").foregroundStyle(.secondary)
                }
                Picker("Amount", selection: $bills[i].amountType) {
                    Text("Same every time").tag(AmountType.fixed)
                    Text("Changes each time").tag(AmountType.variable)
                }
                .pickerStyle(.segmented)
                if bills[i].amountType == .fixed {
                    TextField("Amount (optional)", text: $amounts[i]).keyboardType(.decimalPad)
                }
            } header: {
                if i == 0 { Text("🧾 Bills — they show up on Reminders each month, week or day") }
            }
        }
        Section("Currency") {
            TextField("USD", text: $currency).textInputAutocapitalization(.characters).autocorrectionDisabled()
        }
    }

    private var reviewStep: some View {
        Section {
            LabeledContent("🏠 Home", value: "\(name) · \(address)")
            LabeledContent("👥 People", value: roommates.isEmpty ? "Just you for now" : people.joined(separator: ", "))
            LabeledContent("🧹 Chores", value: chores.map { $0.chore.assignmentMode == .open ? "\($0.chore.name) (anyone)" : "\($0.chore.name) (\(rotationLabel($0.excluded).lowercased()))" }.joined(separator: ", "))
            LabeledContent("🛒 Quick-add", value: groceries.isEmpty ? "None" : groceries.map(\.name).joined(separator: ", "))
            LabeledContent("🧾 Bills", value: bills.map { "\($0.icon) \($0.name)" }.joined(separator: ", "))
        } header: {
            Text("✅ Review")
        } footer: {
            Text(roommates.isEmpty
                 ? "Invite people later with the invite code on the home's screen. You can change everything in Settings."
                 : "Looks right? Tap Create. You can change everything later in Settings.")
        }
    }

    // MARK: Logic

    /// "Everyone" · "Everyone except Bea" · "Ann, Cy" · "Nobody yet"
    private func rotationLabel(_ excluded: Set<Int>) -> String {
        let left = excluded.filter { $0 < people.count }.sorted()
        if left.isEmpty { return "Everyone" }
        let included = people.indices.filter { !left.contains($0) }.map { people[$0] }
        if included.isEmpty { return "Nobody yet" }
        if left.count <= 2 && included.count > left.count {
            return "Everyone except " + left.map { people[$0] }.joined(separator: " & ")
        }
        return included.joined(separator: ", ")
    }

    private func duplicate(_ names: [String]) -> String? {
        var seen = Set<String>()
        for n in names.map({ $0.trimmingCharacters(in: .whitespaces).lowercased() }) {
            if !seen.insert(n).inserted { return n }
        }
        return nil
    }

    private func blank(_ s: String) -> Bool { s.trimmingCharacters(in: .whitespaces).isEmpty }

    private func problem() -> String? {
        switch step {
        case .home:
            if blank(name) { return "Give your home a name" }
            if blank(address) { return "Add the home's address" }
            if blank(timezone) { return "Add a timezone, e.g. America/New_York" }
            return nil
        case .roommates:
            if roommates.contains(where: blank) { return "Every roommate needs a name" }
            if let d = duplicate(people) { return "Two people are called “\(d)”: names must be different" }
            return nil
        case .chores:
            if chores.contains(where: { blank($0.chore.name) }) { return "Every chore needs a name" }
            if let d = duplicate(chores.map(\.chore.name)) { return "Two chores are called “\(d)”" }
            if chores.contains(where: { $0.chore.assignmentMode == .rotation && people.indices.allSatisfy($0.excluded.contains) }) {
                return "Every “take turns” chore needs at least one person"
            }
            return nil
        case .groceries:
            if groceries.contains(where: { blank($0.name) }) { return "Every grocery item needs a name" }
            if let d = duplicate(groceries.map(\.name)) { return "Two items are called “\(d)”" }
            return nil
        case .bills:
            if bills.contains(where: { blank($0.name) }) { return "Every bill needs a name" }
            if let d = duplicate(bills.map(\.name)) { return "Two bills are called “\(d)”" }
            if bills.indices.contains(where: { bills[$0].amountType == .fixed && (Money.cents(amounts[$0]) ?? 0) < 0 }) {
                return "Amounts must be numbers, like 60 or 1250.50"
            }
            let code = currency.trimmingCharacters(in: .whitespaces)
            if code.count != 3 || !code.allSatisfy(\.isLetter) { return "Currency is a 3-letter code, like USD or INR" }
            return nil
        case .review:
            return nil
        }
    }

    private func next() {
        error = problem()
        guard error == nil else { return }
        if step == .home { prefill() }
        step = steps[index + 1]
    }

    /// Prefill each list to its count, keeping anything already edited.
    private func prefill() {
        roommates = Array(roommates.prefix(roommateCount))
        while roommates.count < roommateCount { roommates.append("Roommate \(roommates.count + 2)") }

        chores = resize(chores.map { var c = $0; c.excluded = c.excluded.filter { $0 <= roommateCount }; return c },
                        to: choreCount, defaults: template.chores.map { WizardChore(chore: $0) }, name: \.chore.name,
                        blank: WizardChore(chore: SetupChore(name: "", frequency: .daily, assignmentMode: .rotation)))
        groceries = resize(groceries, to: groceryCount, defaults: template.groceries, name: \.name,
                           blank: SetupGrocery(name: "", categoryKey: "other"))
        bills = resize(bills, to: billCount, defaults: template.bills, name: \.name,
                       blank: SetupBill(name: "", icon: "🧾", payerMode: .anyone, payerName: nil, frequency: .monthly, dueDay: 1, amountType: .fixed, amountCents: nil))
        amounts = bills.indices.map { i in
            i < amounts.count ? amounts[i] : bills[i].amountCents.map { String(format: "%.2f", Double($0) / 100) } ?? ""
        }
    }

    private func resize<T>(_ list: [T], to count: Int, defaults: [T], name: KeyPath<T, String>, blank: T) -> [T] {
        if count <= list.count { return Array(list.prefix(count)) }
        let taken = Set(list.map { $0[keyPath: name].lowercased() })
        var extra = defaults.filter { !taken.contains($0[keyPath: name].lowercased()) }
        var out = list
        while out.count < count { out.append(extra.isEmpty ? blank : extra.removeFirst()) }
        return out
    }

    private func create() async {
        creating = true
        defer { creating = false }
        let setup = HouseholdSetup(
            name: name.trimmingCharacters(in: .whitespaces),
            address: address.trimmingCharacters(in: .whitespaces),
            timezone: timezone.trimmingCharacters(in: .whitespaces),
            roommates: roommates.map { $0.trimmingCharacters(in: .whitespaces) },
            chores: chores.map { c in
                var chore = c.chore
                chore.name = chore.name.trimmingCharacters(in: .whitespaces)
                let left = c.excluded.filter { $0 < people.count }
                chore.people = chore.assignmentMode == .rotation && !left.isEmpty
                    ? people.indices.filter { !left.contains($0) }.map { people[$0] } : nil
                return chore
            },
            groceries: groceries.map { SetupGrocery(name: $0.name.trimmingCharacters(in: .whitespaces), categoryKey: $0.categoryKey) },
            bills: bills.indices.map { i in
                var b = bills[i]
                b.name = b.name.trimmingCharacters(in: .whitespaces)
                b.payerName = b.payerMode == .one ? b.payerName : nil
                b.dueDay = b.frequency == .daily ? 1 : b.dueDay
                b.amountCents = b.amountType == .fixed ? Money.cents(amounts[i]) : nil
                return b
            },
            currency: currency.trimmingCharacters(in: .whitespaces).uppercased()
        )
        do {
            onCreated(try await APIClient.shared.setupHousehold(setup))
        } catch {
            self.error = error.localizedDescription
        }
    }
}
