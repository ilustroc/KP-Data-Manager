<?php

namespace App\Mail;

use DateTimeImmutable;
use DateTimeInterface;
use DateTimeZone;
use Illuminate\Bus\Queueable;
use Illuminate\Mail\Mailable;
use Illuminate\Mail\Mailables\Content;
use Illuminate\Mail\Mailables\Envelope;
use Illuminate\Queue\SerializesModels;

class ManagementHistoryReportMail extends Mailable
{
    use Queueable, SerializesModels;

    public function __construct(
        public readonly DateTimeImmutable $generatedAt,
        public readonly ?DateTimeImmutable $periodFrom = null,
        public readonly ?DateTimeImmutable $periodTo = null,
        public readonly ?int $recordCount = null,
        public readonly ?string $filename = null,
        public readonly ?string $downloadUrl = null,
    ) {}

    /**
     * Get the message envelope.
     */
    public function envelope(): Envelope
    {
        return new Envelope(
            subject: (string) config(
                'reports.management_history.subject',
                'Reporte histórico de gestiones',
            ),
        );
    }

    /**
     * Get the message content definition.
     */
    public function content(): Content
    {
        return new Content(
            view: 'mail.management-history-report',
            with: [
                'generatedAtDisplay' => $this->formatDateTime($this->generatedAt),
                'periodFromDisplay' => $this->formatDate($this->periodFrom),
                'periodToDisplay' => $this->formatDate($this->periodTo),
                'recordCount' => $this->recordCount,
                'filename' => $this->filename,
                'downloadUrl' => $this->downloadUrl,
            ],
        );
    }

    private function formatDateTime(DateTimeInterface $date): string
    {
        return $date
            ->setTimezone($this->reportTimezone())
            ->format('d/m/Y H:i');
    }

    private function formatDate(?DateTimeInterface $date): ?string
    {
        return $date
            ?->setTimezone($this->reportTimezone())
            ->format('d/m/Y');
    }

    private function reportTimezone(): DateTimeZone
    {
        return new DateTimeZone((string) config('reports.management_history.timezone', 'America/Lima'));
    }
}
