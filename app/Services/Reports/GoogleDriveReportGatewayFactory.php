<?php

namespace App\Services\Reports;

use Google\Client;
use Google\Service\Drive;

class GoogleDriveReportGatewayFactory
{
    public function make(string $credentialsPath): GoogleDriveReportGateway
    {
        $client = new Client;
        $client->setApplicationName('KP Data Manager');
        $client->setAuthConfig($credentialsPath);
        $client->setScopes([Drive::DRIVE]);

        return new GoogleDriveReportGateway($client, new Drive($client));
    }
}
