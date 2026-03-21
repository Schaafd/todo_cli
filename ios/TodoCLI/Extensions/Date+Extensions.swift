import Foundation

extension Date {
    var isToday: Bool {
        Calendar.current.isDateInToday(self)
    }

    var isTomorrow: Bool {
        Calendar.current.isDateInTomorrow(self)
    }

    var isYesterday: Bool {
        Calendar.current.isDateInYesterday(self)
    }

    var isPast: Bool {
        self < Date()
    }

    var isThisWeek: Bool {
        Calendar.current.isDate(self, equalTo: Date(), toGranularity: .weekOfYear)
    }

    var relativeDescription: String {
        if isToday {
            return "Today"
        } else if isTomorrow {
            return "Tomorrow"
        } else if isYesterday {
            return "Yesterday"
        } else if isPast {
            let days = Calendar.current.dateComponents([.day], from: self, to: Date()).day ?? 0
            if days < 7 {
                return "\(days)d ago"
            } else if days < 30 {
                let weeks = days / 7
                return "\(weeks)w ago"
            } else {
                return shortFormatted
            }
        } else {
            let days = Calendar.current.dateComponents([.day], from: Date(), to: self).day ?? 0
            if days < 7 {
                let formatter = DateFormatter()
                formatter.dateFormat = "EEEE"
                return formatter.string(from: self)
            } else {
                return shortFormatted
            }
        }
    }

    var shortFormatted: String {
        let formatter = DateFormatter()
        formatter.dateFormat = Calendar.current.isDate(self, equalTo: Date(), toGranularity: .year)
            ? "MMM d"
            : "MMM d, yyyy"
        return formatter.string(from: self)
    }

    var timeFormatted: String {
        let formatter = DateFormatter()
        formatter.dateStyle = .none
        formatter.timeStyle = .short
        return formatter.string(from: self)
    }

    static func pomodoroFormatted(seconds: Int) -> String {
        let minutes = seconds / 60
        let secs = seconds % 60
        return String(format: "%02d:%02d", minutes, secs)
    }
}
