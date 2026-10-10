<?php

namespace App\Services\Reports;

use Illuminate\Support\Str;

class ManagementHistoryReportRecipients
{
    /**
     * @return list<string>
     */
    public function configured(): array
    {
        $configured = config('reports.management_history.recipients', '');

        if (! is_string($configured)) {
            throw InvalidReportRecipients::invalidConfiguration();
        }

        return $this->parse($configured);
    }

    /**
     * @return list<string>
     */
    public function parse(string $configured): array
    {
        $recipients = [];
        $seen = [];

        foreach (explode(',', $configured) as $candidate) {
            $email = trim($candidate);

            if ($email === '') {
                continue;
            }

            if (filter_var($email, FILTER_VALIDATE_EMAIL) === false) {
                throw InvalidReportRecipients::invalidAddress();
            }

            $deduplicationKey = Str::lower($email);

            if (isset($seen[$deduplicationKey])) {
                continue;
            }

            $seen[$deduplicationKey] = true;
            $recipients[] = $email;
        }

        if ($recipients === []) {
            throw InvalidReportRecipients::noneConfigured();
        }

        return $recipients;
    }
}
