<?php

namespace App\Services\Reports;

class ManagementHistoryReportPhone
{
    /**
     * @return false|string|null False means the source had content but was invalid.
     */
    public function normalize(mixed $value): false|string|null
    {
        if ($value === null) {
            return null;
        }

        $source = trim((string) $value);

        if ($source === '') {
            return null;
        }

        if (preg_match('/\A[0-9\s+\-.,\/*()]+\z/u', $source) !== 1) {
            return false;
        }

        $digits = preg_replace('/[\s+\-.,\/*()]+/u', '', $source);

        if ($digits === null) {
            return false;
        }

        if (strlen($digits) === 11 && str_starts_with($digits, '51')) {
            $digits = substr($digits, 2);
        }

        if (preg_match('/\A9[0-9]{8}\z/', $digits) !== 1) {
            return false;
        }

        return $digits;
    }
}
