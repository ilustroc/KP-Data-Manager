<?php

namespace App\Services\Reports;

interface ManagementHistoryReportStorage
{
    public function store(ManagementHistoryExport $export): StoredManagementHistoryReport;
}
